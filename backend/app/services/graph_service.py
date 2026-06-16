"""Graph data loading, visualization, and browsing service."""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from app.config import DATA_ROOT
from app.models.schemas import GraphData, GraphEdge, GraphNode, GraphStats, PaginatedResponse

log = logging.getLogger("graphrag-backend")

# ── Color palette for entity types ───────────────────────────────────────
TYPE_COLORS = {
    "\u4eba\u7269": "#FF6B6B",
    "\u6c11\u65cf/\u65d7\u7c4d": "#FF9F43",
    "\u5236\u5ea6/\u653f\u7b56": "#4ECDC4",
    "\u5730\u70b9/\u533a\u57df": "#45B7D1",
    "\u4e8b\u4ef6": "#F9CA24",
    "\u65f6\u95f4/\u5e74\u4ee3": "#A29BFE",
    "\u5b98\u804c/\u7235\u4f4d": "#7BED9F",
    "\u5e99\u53f7/\u8c25\u53f7": "#E056A0",
    "\u6570\u636e/\u7edf\u8ba1": "#F78FB3",
    # English defaults
    "person": "#FF6B6B",
    "organization": "#4ECDC4",
    "location": "#45B7D1",
    "event": "#F9CA24",
    "concept": "#A29BFE",
    "technology": "#7BED9F",
    "OTHER": "#636E72",
    "\u5176\u4ed6": "#636E72",
}


def _color_for_type(t: str) -> str:
    return TYPE_COLORS.get(str(t).lower(), TYPE_COLORS.get(str(t), TYPE_COLORS["OTHER"]))


def load_parquet(dataset_path: str, table: str) -> pd.DataFrame | None:
    """Load a parquet table from a dataset's output/ directory."""
    p = Path(dataset_path) / "output" / f"{table}.parquet"
    if p.exists():
        try:
            return pd.read_parquet(p)
        except Exception as e:
            log.warning("Failed to load %s: %s", p, e)
    return None


def _dataset_output_dir(dataset_id: str) -> Path:
    return DATA_ROOT / dataset_id / "output"


def _ensure_dataset(dataset_id: str) -> None:
    if not (DATA_ROOT / dataset_id).is_dir():
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Dataset '{dataset_id}' not found")


def get_graph_data(
    dataset_id: str,
    types: list[str] | None = None,
    limit: int = 200,
) -> GraphData:
    """Build JSON graph data (nodes + edges) for frontend visualization."""
    _ensure_dataset(dataset_id)
    output = _dataset_output_dir(dataset_id)

    entities = load_parquet(str(DATA_ROOT / dataset_id), "entities")
    relationships = load_parquet(str(DATA_ROOT / dataset_id), "relationships")

    if entities is None or entities.empty:
        return GraphData(nodes=[], edges=[])

    ents = entities.copy()
    rels = relationships.copy() if relationships is not None else pd.DataFrame()

    # Filter by entity types
    if types and "type" in ents.columns:
        ents = ents[ents["type"].isin(types)]
        if "source" in rels.columns:
            visible = set(ents["title"].tolist())
            rels = rels[rels["source"].isin(visible) & rels["target"].isin(visible)]

    # Apply limit
    if len(ents) > limit:
        ents = ents.head(limit)
        if "source" in rels.columns:
            visible = set(ents["title"].tolist())
            rels = rels[rels["source"].isin(visible) & rels["target"].isin(visible)]

    # Calculate connection counts for node sizing
    connection_counts: dict[str, int] = {}
    if "source" in rels.columns and "target" in rels.columns:
        for _, row in rels.iterrows():
            src = str(row.get("source", ""))
            tgt = str(row.get("target", ""))
            connection_counts[src] = connection_counts.get(src, 0) + 1
            connection_counts[tgt] = connection_counts.get(tgt, 0) + 1

    # Build nodes
    nodes: list[GraphNode] = []
    for _, row in ents.iterrows():
        title = str(row.get("title", row.get("name", "?")))
        desc = str(row.get("description", ""))
        etype = str(row.get("type", "OTHER"))
        conn_count = connection_counts.get(title, 0)
        # Size based on connections: base 10, +3 per connection, max 50
        size = min(10.0 + conn_count * 3.0, 50.0)
        nodes.append(GraphNode(
            id=title,
            label=title,
            type=etype,
            description=desc[:300],
            color=_color_for_type(etype),
            size=size,
        ))

    # Build edges
    edges: list[GraphEdge] = []
    visible_titles = {n.id for n in nodes}
    if "source" in rels.columns and "target" in rels.columns:
        for _, row in rels.iterrows():
            src = str(row.get("source", ""))
            tgt = str(row.get("target", ""))
            desc = str(row.get("description", ""))
            weight = float(row.get("weight", 1.0)) if "weight" in rels.columns else 1.0
            if src in visible_titles and tgt in visible_titles:
                edges.append(GraphEdge(**{
                    "from": src,
                    "to": tgt,
                    "label": desc[:200],
                    "weight": weight,
                }))

    return GraphData(nodes=nodes, edges=edges)


def get_entities(dataset_id: str, page: int = 1, page_size: int = 20) -> PaginatedResponse:
    """Return paginated entities."""
    _ensure_dataset(dataset_id)
    df = load_parquet(str(DATA_ROOT / dataset_id), "entities")
    if df is None or df.empty:
        return PaginatedResponse(items=[], total=0, page=page, page_size=page_size)

    # Select display columns
    cols = [c for c in ["title", "type", "description", "human_readable_id"] if c in df.columns]
    display = df[cols] if cols else df

    total = len(display)
    start = (page - 1) * page_size
    end = start + page_size
    items = display.iloc[start:end].to_dict(orient="records")

    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size)


def get_relationships(dataset_id: str, page: int = 1, page_size: int = 20) -> PaginatedResponse:
    """Return paginated relationships."""
    _ensure_dataset(dataset_id)
    df = load_parquet(str(DATA_ROOT / dataset_id), "relationships")
    if df is None or df.empty:
        return PaginatedResponse(items=[], total=0, page=page, page_size=page_size)

    cols = [c for c in ["source", "target", "description", "human_readable_id"] if c in df.columns]
    display = df[cols] if cols else df

    total = len(display)
    start = (page - 1) * page_size
    end = start + page_size
    items = display.iloc[start:end].to_dict(orient="records")

    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size)


def get_communities(dataset_id: str) -> list[dict]:
    """Return all communities (summary view)."""
    _ensure_dataset(dataset_id)
    df = load_parquet(str(DATA_ROOT / dataset_id), "community_reports")
    if df is None or df.empty:
        return []

    # Select columns for summary view
    want_cols = ["title", "human_readable_id", "community", "rating", "rank"]
    cols = [c for c in want_cols if c in df.columns]
    if not cols:
        return df.to_dict(orient="records")

    result = df[cols].to_dict(orient="records")

    # Ensure every record has an 'id' field (frontend uses it as rowKey)
    # and a 'rating' field (normalize 'rank' → 'rating')
    for rec in result:
        if "id" not in rec:
            rec["id"] = rec.get("human_readable_id", rec.get("community", ""))
        if "rating" not in rec and "rank" in rec:
            rec["rating"] = rec["rank"]
    return result


def get_community_detail(dataset_id: str, community_id: str) -> dict | None:
    """Return full detail for a single community report."""
    _ensure_dataset(dataset_id)
    df = load_parquet(str(DATA_ROOT / dataset_id), "community_reports")
    if df is None or df.empty:
        return None

    # Try matching by human_readable_id, community, or title
    for col in ["human_readable_id", "community", "title"]:
        if col in df.columns:
            match = df[df[col].astype(str) == str(community_id)]
            if not match.empty:
                row = match.iloc[0]
                result = row.to_dict()

                # Parse JSON-encoded fields
                import json
                for json_field in ("full_content_json", "findings"):
                    if json_field in result and isinstance(result[json_field], str):
                        try:
                            result[json_field] = json.loads(result[json_field])
                        except Exception:
                            pass

                # If 'report' exists but 'summary' doesn't, use report as summary
                if "report" in result and not result.get("summary"):
                    result["summary"] = result["report"]

                # Normalize 'rank' → 'rating' if needed
                if "rating" not in result and "rank" in result:
                    result["rating"] = result["rank"]

                return result
    return None


def get_graph_stats(dataset_id: str) -> GraphStats:
    """Return summary statistics for the graph."""
    _ensure_dataset(dataset_id)

    entities = load_parquet(str(DATA_ROOT / dataset_id), "entities")
    relationships = load_parquet(str(DATA_ROOT / dataset_id), "relationships")
    communities = load_parquet(str(DATA_ROOT / dataset_id), "community_reports")

    entity_count = len(entities) if entities is not None else 0
    relationship_count = len(relationships) if relationships is not None else 0
    community_count = len(communities) if communities is not None else 0

    entity_types: dict[str, int] = {}
    if entities is not None and "type" in entities.columns:
        entity_types = entities["type"].value_counts().to_dict()
        # Ensure keys are strings
        entity_types = {str(k): int(v) for k, v in entity_types.items()}

    return GraphStats(
        entity_count=entity_count,
        relationship_count=relationship_count,
        community_count=community_count,
        entity_types=entity_types,
    )


def search_entity_names(dataset_id: str, query: str, limit: int = 20) -> list[dict]:
    """Fuzzy-search entity names, returning top matches."""
    _ensure_dataset(dataset_id)
    df = load_parquet(str(DATA_ROOT / dataset_id), "entities")
    if df is None or df.empty:
        return []

    title_col = "title" if "title" in df.columns else "name"
    if title_col not in df.columns:
        return []

    q = query.lower().strip()
    if not q:
        return []

    # Case-insensitive substring match, then sort by relevance
    matches = df[df[title_col].astype(str).str.lower().str.contains(q, na=False)]

    # Sort: exact match first, then starts-with, then contains
    def _sort_key(title: str) -> tuple:
        t = title.lower()
        if t == q:
            return (0, t)
        if t.startswith(q):
            return (1, t)
        return (2, t)

    titles = matches[title_col].astype(str).tolist()
    titles.sort(key=_sort_key)
    titles = titles[:limit]

    # Build result with type info
    result = []
    for title in titles:
        row = matches[matches[title_col].astype(str) == title].iloc[0]
        etype = str(row.get("type", ""))
        result.append({"name": title, "type": etype})
    return result


def get_entity_neighborhood(
    dataset_id: str,
    entity_name: str,
    depth: int = 3,
) -> GraphData:
    """BFS from an entity through relationships, returning subgraph up to N levels."""
    _ensure_dataset(dataset_id)

    entities_df = load_parquet(str(DATA_ROOT / dataset_id), "entities")
    rels_df = load_parquet(str(DATA_ROOT / dataset_id), "relationships")

    if entities_df is None or entities_df.empty:
        return GraphData(nodes=[], edges=[])

    title_col = "title" if "title" in entities_df.columns else "name"

    # Build adjacency map: entity_name -> set of (neighbor_name, description, weight)
    adjacency: dict[str, list[tuple[str, str, float]]] = {}
    if rels_df is not None and "source" in rels_df.columns and "target" in rels_df.columns:
        for _, row in rels_df.iterrows():
            src = str(row.get("source", ""))
            tgt = str(row.get("target", ""))
            desc = str(row.get("description", ""))[:200]
            weight = float(row.get("weight", 1.0)) if "weight" in rels_df.columns else 1.0
            adjacency.setdefault(src, []).append((tgt, desc, weight))
            adjacency.setdefault(tgt, []).append((src, desc, weight))

    # BFS from entity_name
    visited: dict[str, int] = {}  # entity_name -> level
    queue = [(entity_name, 0)]
    visited[entity_name] = 0
    collected_edges: list[dict] = []

    while queue:
        current, level = queue.pop(0)
        if level >= depth:
            continue
        for neighbor, desc, weight in adjacency.get(current, []):
            collected_edges.append({
                "from": current,
                "to": neighbor,
                "label": desc,
                "weight": weight,
                "level": level + 1,
            })
            if neighbor not in visited:
                visited[neighbor] = level + 1
                queue.append((neighbor, level + 1))

    # Build entity lookup
    entity_map: dict[str, pd.Series] = {}
    if title_col in entities_df.columns:
        for _, row in entities_df.iterrows():
            name = str(row.get(title_col, ""))
            entity_map[name] = row

    # Build nodes for visited entities
    nodes: list[GraphNode] = []
    connection_counts: dict[str, int] = {}
    for edge in collected_edges:
        connection_counts[edge["from"]] = connection_counts.get(edge["from"], 0) + 1
        connection_counts[edge["to"]] = connection_counts.get(edge["to"], 0) + 1

    for name, level in visited.items():
        row = entity_map.get(name)
        etype = str(row.get("type", "OTHER")) if row is not None else "OTHER"
        desc = str(row.get("description", ""))[:300] if row is not None else ""
        conn = connection_counts.get(name, 0)
        size = min(10.0 + conn * 3.0, 50.0)
        # Root entity gets larger size
        if level == 0:
            size = max(size, 35.0)
        nodes.append(GraphNode(
            id=name,
            label=name,
            type=etype,
            description=desc,
            color=_color_for_type(etype),
            size=size,
        ))

    # Build edges (deduplicate by from->to pair)
    seen_edges: set[str] = set()
    edges: list[GraphEdge] = []
    for e in collected_edges:
        key = f"{e['from']}->{e['to']}"
        if key not in seen_edges:
            seen_edges.add(key)
            edges.append(GraphEdge(**{
                "from": e["from"],
                "to": e["to"],
                "label": e["label"],
                "weight": e["weight"],
            }))

    return GraphData(nodes=nodes, edges=edges)
