"""Graph data loading, visualization, and browsing service.

Reads the knowledge graph directly from each dataset's LightRAG storage via
``rag.lightrag.get_knowledge_graph``. Multimodal entities (image/table/equation)
are surfaced with distinct types/colors, and image entities resolve a
dataset-relative thumbnail path extracted from their source chunk.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from fastapi import HTTPException

from app.config import DATA_ROOT
from app.models.schemas import (
    GraphData,
    GraphEdge,
    GraphNode,
    GraphStats,
    PaginatedResponse,
)
from app.services.rag_engine import dataset_root, get_lightrag, parse_output_dir

log = logging.getLogger("graphrag-backend")

_GRAPH_FIELD_SEP = "<SEP>"
_IMAGE_PATH_RE = re.compile(r"Image Path:\s*([^\r\n]+)")
_MAX_GRAPH_NODES = 100_000

# 需要携带可解析截图的多模态实体类型。
# image/table 的 chunk 内嵌了 "Image Path:"；chart/equation 的 chunk 没有，
# 因此后两者的截图从 MinerU 的 content_list.json 中解析。
_MULTIMODAL_TYPES = {"image", "table", "chart", "equation"}

# ── Color palette by entity type ─────────────────────────────────────────
TYPE_COLORS = {
    "person": "#FF6B6B",
    "organization": "#4ECDC4",
    "location": "#45B7D1",
    "geo": "#45B7D1",
    "event": "#F9CA24",
    "concept": "#A29BFE",
    "category": "#A29BFE",
    "technology": "#7BED9F",
    # RAG-Anything 产生的多模态实体类型
    "image": "#E056A0",
    "table": "#F78FB3",
    "chart": "#FF9FF3",
    "equation": "#FDA7DF",
    "OTHER": "#636E72",
}


def _color_for_type(t: str) -> str:
    key = str(t).strip()
    return TYPE_COLORS.get(key.lower(), TYPE_COLORS.get(key, TYPE_COLORS["OTHER"]))


def _ensure_dataset(dataset_id: str) -> None:
    if not (DATA_ROOT / dataset_id).is_dir():
        raise HTTPException(status_code=404, detail=f"Dataset '{dataset_id}' not found")


def _node_type(node) -> str:
    # LightRAG 1.5 的 KnowledgeGraphNode.labels[0] 是实体“名称”而非类型；
    # 真正的类型在 properties["entity_type"]。优先取它，才能正确识别多模态
    # 类型（image/table/…）、正确着色/过滤，并让详情面板显示类型而非名称。
    etype = node.properties.get("entity_type")
    if etype:
        return str(etype)
    if node.labels:
        return str(node.labels[0])
    return "OTHER"


def _normalize_image(dataset_id: str, raw_path: str) -> str | None:
    root = dataset_root(dataset_id).resolve()
    p = Path(raw_path)
    candidates = [p] if p.is_absolute() else [root / raw_path, root / "output" / raw_path]
    for cand in candidates:
        try:
            resolved = cand.resolve()
        except Exception:
            continue
        if resolved.exists() and resolved.is_relative_to(root):
            return str(resolved.relative_to(root))
    return None


async def _build_graph_data(
    dataset_id: str, node_label: str, max_depth: int, max_nodes: int,
    types: list[str] | None = None,
) -> GraphData:
    lightrag = await get_lightrag(dataset_id)
    kg = await lightrag.get_knowledge_graph(
        node_label=node_label, max_depth=max_depth, max_nodes=max_nodes
    )

    # 按度数决定节点大小
    degree: dict[str, int] = {}
    for e in kg.edges:
        degree[e.source] = degree.get(e.source, 0) + 1
        degree[e.target] = degree.get(e.target, 0) + 1

    type_filter = {t.lower() for t in types} if types else None
    content_lists = _load_content_lists(dataset_id)

    nodes: list[GraphNode] = []
    visible: set[str] = set()
    for n in kg.nodes:
        etype = _node_type(n)
        if type_filter and etype.lower() not in type_filter:
            continue
        conn = degree.get(n.id, 0)
        size = min(10.0 + conn * 3.0, 50.0)
        image = None
        if etype.lower() in _MULTIMODAL_TYPES:
            raw = await _resolve_image_chunk_path(lightrag, n, content_lists)
            if raw:
                image = _normalize_image(dataset_id, raw)
        nodes.append(GraphNode(
            id=n.id,
            label=str(n.properties.get("entity_id", n.id)),
            type=etype,
            description=str(n.properties.get("description", ""))[:300],
            color=_color_for_type(etype),
            size=size,
            image=image,
        ))
        visible.add(n.id)

    edges: list[GraphEdge] = []
    seen: set[str] = set()
    for e in kg.edges:
        if e.source not in visible or e.target not in visible:
            continue
        key = f"{e.source}->{e.target}"
        if key in seen:
            continue
        seen.add(key)
        desc = str(e.properties.get("description", "") or e.properties.get("keywords", ""))
        weight = float(e.properties.get("weight", 1.0) or 1.0)
        edges.append(GraphEdge(**{
            "from": e.source, "to": e.target, "label": desc[:200], "weight": weight,
        }))

    return GraphData(nodes=nodes, edges=edges)


def _load_content_lists(
    dataset_id: str,
) -> dict[str, dict[tuple[str, int], list[str]]]:
    """索引每个文档的 MinerU ``content_list.json`` 截图。

    返回 ``{文档名: {(条目类型, 页码): [绝对图片路径, ...]}}``。chart（及
    equation）实体的 chunk 不含内嵌的 ``Image Path:``，其截图仅存在于此，
    按 MinerU 的条目类型与页码索引。json 中的 img_path 相对于该 json 所在目录，
    因此解析为绝对路径，再交由 ``_normalize_image`` 校验。
    """
    result: dict[str, dict[tuple[str, int], list[str]]] = {}
    out_dir = parse_output_dir(dataset_id)
    if not out_dir.is_dir():
        return result
    suffix = "_content_list.json"
    for cl in out_dir.rglob(f"*{suffix}"):
        stem = cl.name[: -len(suffix)]
        try:
            items = json.loads(cl.read_text(encoding="utf-8"))
        except Exception:
            continue
        index: dict[tuple[str, int], list[str]] = {}
        for item in items if isinstance(items, list) else []:
            img = item.get("img_path")
            if not img:
                continue
            itype = str(item.get("type", "")).lower()
            page = int(item.get("page_idx", 0) or 0)
            index.setdefault((itype, page), []).append(str((cl.parent / img).resolve()))
        result[stem] = index
    return result


async def _resolve_image_chunk_path(
    lightrag, node, content_lists: dict[str, dict[tuple[str, int], list[str]]]
) -> str | None:
    source_id = node.properties.get("source_id")
    if not source_id:
        return None
    chunk_id = str(source_id).split(_GRAPH_FIELD_SEP)[0]
    try:
        chunk = await lightrag.text_chunks.get_by_id(chunk_id)
    except Exception:
        return None
    if not isinstance(chunk, dict):
        return None
    m = _IMAGE_PATH_RE.search(chunk.get("content", ""))
    if m:
        return m.group(1).strip()
    # chart/equation 的 chunk 不含内嵌路径——用 chunk 的 MinerU 条目类型 +
    # 页码去 content_list 索引中匹配。匹配后 pop 出该路径，使同一页多个同类型
    # 条目能分别取到不同的图片。
    itype = str(chunk.get("original_type", "")).lower()
    page = chunk.get("page_idx")
    if not itype or page is None:
        return None
    stem = Path(str(chunk.get("file_path", ""))).stem
    paths = (content_lists.get(stem) or {}).get((itype, int(page)))
    return paths.pop(0) if paths else None


# ── Public API ────────────────────────────────────────────────────────────
async def get_graph_data(
    dataset_id: str, types: list[str] | None = None, limit: int = 200
) -> GraphData:
    """Build JSON graph data (nodes + edges) for frontend visualization."""
    _ensure_dataset(dataset_id)
    try:
        return await _build_graph_data(
            dataset_id, node_label="*", max_depth=3, max_nodes=limit, types=types
        )
    except Exception as e:
        log.exception("get_graph_data failed for %s", dataset_id)
        return GraphData(nodes=[], edges=[])


async def get_entity_neighborhood(
    dataset_id: str, entity_name: str, depth: int = 3
) -> GraphData:
    """Return subgraph of an entity's N-level neighborhood."""
    _ensure_dataset(dataset_id)
    try:
        return await _build_graph_data(
            dataset_id, node_label=entity_name, max_depth=depth, max_nodes=_MAX_GRAPH_NODES
        )
    except Exception as e:
        log.exception("get_entity_neighborhood failed for %s", dataset_id)
        return GraphData(nodes=[], edges=[])


async def _full_graph(dataset_id: str) -> GraphData:
    return await _build_graph_data(
        dataset_id, node_label="*", max_depth=1, max_nodes=_MAX_GRAPH_NODES
    )


async def get_graph_stats(dataset_id: str) -> GraphStats:
    """Return summary statistics for the graph."""
    _ensure_dataset(dataset_id)
    try:
        data = await _full_graph(dataset_id)
    except Exception:
        log.exception("get_graph_stats failed for %s", dataset_id)
        return GraphStats(entity_count=0, relationship_count=0, entity_types={})

    entity_types: dict[str, int] = {}
    for n in data.nodes:
        entity_types[n.type] = entity_types.get(n.type, 0) + 1
    return GraphStats(
        entity_count=len(data.nodes),
        relationship_count=len(data.edges),
        entity_types=entity_types,
    )


async def search_entity_names(dataset_id: str, query: str, limit: int = 20) -> list[dict]:
    """Fuzzy-search entity names, returning top matches."""
    _ensure_dataset(dataset_id)
    q = query.lower().strip()
    if not q:
        return []
    try:
        data = await _full_graph(dataset_id)
    except Exception:
        return []

    def _sort_key(name: str) -> tuple:
        t = name.lower()
        if t == q:
            return (0, t)
        if t.startswith(q):
            return (1, t)
        return (2, t)

    matched = [n for n in data.nodes if q in n.id.lower()]
    matched.sort(key=lambda n: _sort_key(n.id))
    return [{"name": n.id, "type": n.type} for n in matched[:limit]]


async def get_entities(dataset_id: str, page: int = 1, page_size: int = 20) -> PaginatedResponse:
    """Return paginated entities."""
    _ensure_dataset(dataset_id)
    try:
        data = await _full_graph(dataset_id)
    except Exception:
        return PaginatedResponse(items=[], total=0, page=page, page_size=page_size)

    items = [
        {"title": n.id, "type": n.type, "description": n.description}
        for n in data.nodes
    ]
    total = len(items)
    start = (page - 1) * page_size
    return PaginatedResponse(
        items=items[start:start + page_size], total=total, page=page, page_size=page_size
    )


async def get_relationships(dataset_id: str, page: int = 1, page_size: int = 20) -> PaginatedResponse:
    """Return paginated relationships."""
    _ensure_dataset(dataset_id)
    try:
        data = await _full_graph(dataset_id)
    except Exception:
        return PaginatedResponse(items=[], total=0, page=page, page_size=page_size)

    items = [
        {"source": e.from_, "target": e.to, "description": e.label, "weight": e.weight}
        for e in data.edges
    ]
    total = len(items)
    start = (page - 1) * page_size
    return PaginatedResponse(
        items=items[start:start + page_size], total=total, page=page, page_size=page_size
    )


async def get_entity_detail(dataset_id: str, name: str) -> dict:
    """Precise entity lookup: node properties + neighbor entity names."""
    _ensure_dataset(dataset_id)
    lightrag = await get_lightrag(dataset_id)
    info = await lightrag.get_entity_info(name)
    props = info.get("graph_data")
    if not props:
        raise HTTPException(status_code=404, detail=f"Entity '{name}' not found")
    edges = await lightrag.chunk_entity_relation_graph.get_node_edges(name) or []
    neighbors = [t for s, t in edges]
    return {"name": name, "properties": props, "neighbors": neighbors}


async def get_relation_detail(dataset_id: str, source: str, target: str) -> dict:
    """Precise relationship lookup between two entities."""
    _ensure_dataset(dataset_id)
    lightrag = await get_lightrag(dataset_id)
    info = await lightrag.get_relation_info(source, target)
    props = info.get("graph_data")
    if not props:
        raise HTTPException(
            status_code=404, detail=f"Relationship '{source}' -> '{target}' not found"
        )
    return {"source": source, "target": target, "properties": props}


def resolve_image_file(dataset_id: str, rel_path: str) -> Path:
    """Validate and resolve a dataset-relative image path to an absolute file.

    Raises HTTPException(404) if the path escapes the dataset or does not exist.
    """
    _ensure_dataset(dataset_id)
    root = dataset_root(dataset_id).resolve()
    candidate = (root / rel_path).resolve()
    if not candidate.is_relative_to(root) or not candidate.is_file():
        raise HTTPException(status_code=404, detail="Image not found")
    return candidate
