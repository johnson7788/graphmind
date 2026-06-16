"""Dataset discovery and management service."""

from __future__ import annotations

import logging
import shutil
from datetime import datetime
from pathlib import Path

import pandas as pd
import yaml

from app.config import DATA_ROOT
from app.models.schemas import DatasetInfo

log = logging.getLogger("graphrag-backend")


def _read_parquet_count(path: Path) -> int:
    """Return row count of a parquet file, or 0 on any error."""
    if not path.exists():
        return 0
    try:
        import pyarrow.parquet as pq
        meta = pq.read_metadata(path)
        return meta.num_rows
    except Exception:
        return 0


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

    output_dir = d / "output"
    entities_file = output_dir / "entities.parquet"
    has_index = entities_file.exists()

    # Index is complete only if all critical tables exist
    _CRITICAL_TABLES = ["entities.parquet", "relationships.parquet",
                        "communities.parquet", "community_reports.parquet",
                        "text_units.parquet"]
    index_complete = has_index and all(
        (output_dir / t).exists() for t in _CRITICAL_TABLES
    )

    # Count rows
    entity_count = _read_parquet_count(output_dir / "entities.parquet")
    relationship_count = _read_parquet_count(output_dir / "relationships.parquet")
    community_count = _read_parquet_count(output_dir / "communities.parquet")

    return DatasetInfo(
        id=dataset_id,
        name=name,
        created=created.strftime("%Y-%m-%d %H:%M"),
        has_index=has_index,
        index_complete=index_complete,
        entity_count=entity_count,
        relationship_count=relationship_count,
        community_count=community_count,
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
