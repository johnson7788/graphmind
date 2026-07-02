"""Tests for app.models.schemas."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models.schemas import (
    DatasetCreate,
    DatasetInfo,
    GraphEdge,
    GraphNode,
    IndexStatus,
    SearchRequest,
    SearchResponse,
)


class TestDatasetCreate:
    def test_valid(self):
        d = DatasetCreate(name="test")
        assert d.name == "test"

    def test_empty_name_rejected(self):
        with pytest.raises(ValidationError):
            DatasetCreate(name="")

    def test_long_name_rejected(self):
        with pytest.raises(ValidationError):
            DatasetCreate(name="x" * 101)

    def test_max_length(self):
        d = DatasetCreate(name="x" * 100)
        assert len(d.name) == 100


class TestDatasetInfo:
    def test_defaults(self):
        d = DatasetInfo(id="t", name="t", created="2024-01-01", has_index=False)
        assert d.index_complete is False
        assert d.entity_count == 0
        assert d.relationship_count == 0

    def test_full(self):
        d = DatasetInfo(
            id="ds", name="DS", created="2024-01-01",
            has_index=True, index_complete=True,
            entity_count=10, relationship_count=5,
        )
        assert d.entity_count == 10


class TestSearchRequest:
    def test_defaults(self):
        r = SearchRequest(query="hello")
        assert r.mode == "mix"
        assert r.multimodal_content is None

    @pytest.mark.parametrize("mode", ["naive", "local", "global", "hybrid", "mix", "basic"])
    def test_valid_modes(self, mode):
        r = SearchRequest(query="q", mode=mode)
        assert r.mode == mode

    def test_invalid_mode(self):
        with pytest.raises(ValidationError):
            SearchRequest(query="q", mode="invalid")

    def test_empty_query_rejected(self):
        with pytest.raises(ValidationError):
            SearchRequest(query="")


class TestSearchResponse:
    def test_basic(self):
        r = SearchResponse(query="q", mode="mix", answer="42")
        assert r.context is None

    def test_with_context(self):
        r = SearchResponse(query="q", mode="mix", answer="a", context="ctx")
        assert r.context == "ctx"


class TestIndexStatus:
    def test_defaults(self):
        s = IndexStatus(dataset_id="ds", status="idle")
        assert s.step == ""
        assert s.progress == 0
        assert s.error is None

    def test_running(self):
        s = IndexStatus(dataset_id="ds", status="running", step="building", progress=50)
        assert s.progress == 50


class TestGraphNode:
    def test_basic(self):
        n = GraphNode(id="1", label="A", type="person", description="desc",
                      color="#FF0000", size=10.0)
        assert n.image is None

    def test_with_image(self):
        n = GraphNode(id="1", label="A", type="image", description="",
                      color="#E056A0", size=10.0, image="output/img.png")
        assert n.image == "output/img.png"


class TestGraphEdge:
    def test_alias(self):
        e = GraphEdge(**{"from": "A", "to": "B", "label": "rel", "weight": 1.0})
        assert e.from_ == "A"
        assert e.to == "B"

    def test_populate_by_name(self):
        e = GraphEdge(from_="A", to="B", label="rel", weight=1.0)
        assert e.from_ == "A"

    def test_serialization(self):
        e = GraphEdge(**{"from": "A", "to": "B", "label": "rel", "weight": 2.5})
        d = e.model_dump(by_alias=True)
        assert d["from"] == "A"
