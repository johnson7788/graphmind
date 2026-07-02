"""Tests for app.services.dataset_service."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException

from app.services import dataset_service


class TestListDatasets:
    def test_empty_when_no_datasets(self, tmp_data_root):
        result = dataset_service.list_datasets()
        assert result == []

    def test_lists_created_datasets(self, tmp_data_root):
        for name in ["alpha", "beta"]:
            ds = tmp_data_root / name
            ds.mkdir()
            (ds / ".demo_meta.yaml").write_text(f"dataset_name: {name}\n")
        result = dataset_service.list_datasets()
        assert len(result) == 2
        names = {d.name for d in result}
        assert names == {"alpha", "beta"}

    def test_skips_files(self, tmp_data_root):
        (tmp_data_root / "not_a_dir.txt").write_text("hi")
        result = dataset_service.list_datasets()
        assert result == []


class TestCreateDataset:
    def test_creates_directory_structure(self, tmp_data_root):
        info = dataset_service.create_dataset("new_ds", "New Dataset")
        assert info.id == "new_ds"
        assert info.name == "New Dataset"
        ds_dir = tmp_data_root / "new_ds"
        assert ds_dir.is_dir()
        assert (ds_dir / "input").is_dir()
        assert (ds_dir / ".demo_meta.yaml").is_file()

    def test_duplicate_raises_409(self, tmp_data_root):
        dataset_service.create_dataset("dup", "Dup")
        with pytest.raises(HTTPException) as exc_info:
            dataset_service.create_dataset("dup", "Dup Again")
        assert exc_info.value.status_code == 409


class TestGetDataset:
    def test_returns_info(self, dataset_dir):
        info = dataset_service.get_dataset("test_ds")
        assert info.id == "test_ds"
        assert info.name == "test_ds"

    def test_missing_raises_404(self, tmp_data_root):
        with pytest.raises(HTTPException) as exc_info:
            dataset_service.get_dataset("nonexistent")
        assert exc_info.value.status_code == 404


class TestDeleteDataset:
    def test_deletes_directory(self, dataset_dir, tmp_data_root):
        assert dataset_dir.is_dir()
        dataset_service.delete_dataset("test_ds")
        assert not dataset_dir.is_dir()

    def test_missing_raises_404(self, tmp_data_root):
        with pytest.raises(HTTPException) as exc_info:
            dataset_service.delete_dataset("nonexistent")
        assert exc_info.value.status_code == 404


class TestGraphCounts:
    def test_no_graphml_returns_zeros(self, dataset_dir):
        n, e = dataset_service._graph_counts(dataset_dir / "rag_storage")
        assert (n, e) == (0, 0)

    def test_with_graphml(self, dataset_dir):
        import networkx as nx
        rag_dir = dataset_dir / "rag_storage"
        rag_dir.mkdir()
        g = nx.Graph()
        g.add_edge("A", "B")
        g.add_edge("B", "C")
        nx.write_graphml(g, rag_dir / "graph_chunk_entity_relation.graphml")
        n, e = dataset_service._graph_counts(rag_dir)
        assert n == 3
        assert e == 2


class TestDatasetInfoFromDir:
    def test_reads_meta_yaml(self, dataset_dir):
        info = dataset_service._dataset_info_from_dir(dataset_dir)
        assert info.name == "test_ds"
        assert info.has_index is False
        assert info.entity_count == 0

    def test_no_meta_yaml_uses_dirname(self, tmp_data_root):
        ds = tmp_data_root / "raw_name"
        ds.mkdir()
        info = dataset_service._dataset_info_from_dir(ds)
        assert info.name == "raw_name"

    def test_with_index(self, dataset_dir):
        import networkx as nx
        rag_dir = dataset_dir / "rag_storage"
        rag_dir.mkdir()
        g = nx.Graph()
        g.add_edge("X", "Y")
        nx.write_graphml(g, rag_dir / "graph_chunk_entity_relation.graphml")
        info = dataset_service._dataset_info_from_dir(dataset_dir)
        assert info.has_index is True
        assert info.index_complete is True
        assert info.entity_count == 2
        assert info.relationship_count == 1
