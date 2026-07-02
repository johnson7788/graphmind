"""Shared test fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def tmp_data_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Override DATA_ROOT in config and all services that import it."""
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setattr("app.config.DATA_ROOT", data)
    for mod in (
        "app.services.dataset_service",
        "app.services.document_service",
        "app.services.graph_service",
        "app.services.search_service",
    ):
        monkeypatch.setattr(f"{mod}.DATA_ROOT", data)
    return data


@pytest.fixture
def client(tmp_data_root: Path) -> TestClient:
    """FastAPI TestClient with tmp data root."""
    from app.main import app
    return TestClient(app)


@pytest.fixture
def dataset_dir(tmp_data_root: Path) -> Path:
    """Create a ready-to-use dataset directory with input/ subfolder."""
    ds = tmp_data_root / "test_ds"
    ds.mkdir()
    (ds / "input").mkdir()
    (ds / ".demo_meta.yaml").write_text("dataset_name: test_ds\n")
    return ds
