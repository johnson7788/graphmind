"""Dataset discovery and management service."""

from __future__ import annotations

import logging
import shutil
from datetime import datetime
from pathlib import Path

import yaml

from app.config import DATA_ROOT
from app.models.schemas import DatasetInfo

log = logging.getLogger("graphrag-backend")

# LightRAG's knowledge-graph file lives under <dataset>/rag_storage/.
_GRAPHML_NAME = "graph_chunk_entity_relation.graphml"


def _graph_counts(rag_storage: Path) -> tuple[int, int]:
    """Return (node_count, edge_count) from the LightRAG GraphML, or (0, 0)."""
    graphml = rag_storage / _GRAPHML_NAME
    if not graphml.exists():
        return 0, 0
    try:
        import networkx as nx
        g = nx.read_graphml(graphml)
        return g.number_of_nodes(), g.number_of_edges()
    except Exception as e:
        log.warning("Failed to read graph for %s: %s", rag_storage, e)
        return 0, 0


def _dataset_info_from_dir(d: Path) -> DatasetInfo:
    """Build a DatasetInfo from a dataset directory."""
    dataset_id = d.name
    name = d.name
    created = datetime.fromtimestamp(d.stat().st_ctime)

    # Read display name from .demo_meta.yaml
    meta_file = d / ".demo_meta.yaml"
    if meta_file.exists():
        try:
            meta = yaml.safe_load(open(meta_file))
            if meta and "dataset_name" in meta:
                name = meta["dataset_name"]
        except Exception:
            pass

    rag_storage = d / "rag_storage"
    graphml = rag_storage / _GRAPHML_NAME
    has_index = graphml.exists()
    entity_count, relationship_count = _graph_counts(rag_storage)
    index_complete = has_index and entity_count > 0

    return DatasetInfo(
        id=dataset_id,
        name=name,
        created=created.strftime("%Y-%m-%d %H:%M"),
        has_index=has_index,
        index_complete=index_complete,
        entity_count=entity_count,
        relationship_count=relationship_count,
    )


def list_datasets() -> list[DatasetInfo]:
    """Scan DATA_ROOT and return all datasets (newest first)."""
    if not DATA_ROOT.exists():
        return []
    results: list[DatasetInfo] = []
    for d in sorted(DATA_ROOT.iterdir(), reverse=True):
        if not d.is_dir():
            continue
        try:
            results.append(_dataset_info_from_dir(d))
        except Exception as e:
            log.warning("Skipping dataset dir %s: %s", d, e)
    return results


def get_dataset(dataset_id: str) -> DatasetInfo:
    """Return info for a single dataset."""
    d = DATA_ROOT / dataset_id
    if not d.is_dir():
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Dataset '{dataset_id}' not found")
    return _dataset_info_from_dir(d)


def create_dataset(dataset_id: str, name: str) -> DatasetInfo:
    """Create a new dataset directory with .demo_meta.yaml."""
    d = DATA_ROOT / dataset_id
    if d.exists():
        from fastapi import HTTPException
        raise HTTPException(status_code=409, detail=f"Dataset '{dataset_id}' already exists")
    d.mkdir(parents=True, exist_ok=True)
    (d / "input").mkdir(exist_ok=True)
    meta = {"dataset_name": name}
    (d / ".demo_meta.yaml").write_text(yaml.dump(meta))
    return _dataset_info_from_dir(d)


def delete_dataset(dataset_id: str) -> None:
    """Delete an entire dataset directory."""
    d = DATA_ROOT / dataset_id
    if not d.is_dir():
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Dataset '{dataset_id}' not found")
    shutil.rmtree(d)
    log.info("Deleted dataset: %s", dataset_id)
