"""Tests for API routers using FastAPI TestClient."""

from __future__ import annotations

from unittest.mock import patch, AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient


class TestHealth:
    def test_health(self, client: TestClient):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


class TestDatasetsRouter:
    def test_list_empty(self, client: TestClient):
        resp = client.get("/api/datasets")
        assert resp.status_code == 200
        assert resp.json()["datasets"] == []

    def test_create_and_get(self, client: TestClient):
        resp = client.post("/api/datasets", json={"name": "my dataset"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "my dataset"
        ds_id = data["id"]

        resp2 = client.get(f"/api/datasets/{ds_id}")
        assert resp2.status_code == 200
        assert resp2.json()["id"] == ds_id

    def test_get_missing(self, client: TestClient):
        resp = client.get("/api/datasets/nonexistent")
        assert resp.status_code == 404

    def test_delete(self, client: TestClient):
        resp = client.post("/api/datasets", json={"name": "to_delete"})
        ds_id = resp.json()["id"]
        resp2 = client.delete(f"/api/datasets/{ds_id}")
        assert resp2.status_code == 200
        assert resp2.json()["deleted"] is True
        # Verify gone
        resp3 = client.get(f"/api/datasets/{ds_id}")
        assert resp3.status_code == 404

    def test_delete_missing(self, client: TestClient):
        resp = client.delete("/api/datasets/nope")
        assert resp.status_code == 404

    def test_list_after_create(self, client: TestClient):
        client.post("/api/datasets", json={"name": "ds1"})
        client.post("/api/datasets", json={"name": "ds2"})
        resp = client.get("/api/datasets")
        assert len(resp.json()["datasets"]) == 2


class TestDocumentsRouter:
    def test_list_empty(self, client: TestClient, dataset_dir):
        resp = client.get("/api/datasets/test_ds/documents")
        assert resp.status_code == 200
        assert resp.json()["documents"] == []

    def test_upload_and_list(self, client: TestClient, dataset_dir):
        resp = client.post(
            "/api/datasets/test_ds/documents",
            files=[("files", ("test.txt", b"hello world", "text/plain"))],
        )
        assert resp.status_code == 200
        assert resp.json()["uploaded"] == 1

        resp2 = client.get("/api/datasets/test_ds/documents")
        docs = resp2.json()["documents"]
        assert len(docs) == 1
        assert docs[0]["name"] == "test.txt"

    def test_upload_bad_extension(self, client: TestClient, dataset_dir):
        resp = client.post(
            "/api/datasets/test_ds/documents",
            files=[("files", ("evil.exe", b"", "application/octet-stream"))],
        )
        assert resp.status_code == 400

    def test_delete_document(self, client: TestClient, dataset_dir):
        client.post(
            "/api/datasets/test_ds/documents",
            files=[("files", ("del.txt", b"data", "text/plain"))],
        )
        resp = client.delete("/api/datasets/test_ds/documents/del.txt")
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True

    def test_delete_missing_document(self, client: TestClient, dataset_dir):
        resp = client.delete("/api/datasets/test_ds/documents/nope.txt")
        assert resp.status_code == 404


class TestIndexingRouter:
    def test_config_status(self, client: TestClient, monkeypatch):
        monkeypatch.setattr("app.config.APP_CONFIG", {"llm": {"api_key": "sk-test", "model": "qwen"}})
        resp = client.get("/api/config/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["configured"] is True
        assert data["model"] == "qwen"

    def test_start_indexing_no_docs(self, client: TestClient, dataset_dir):
        resp = client.post(
            "/api/datasets/test_ds/index",
            json={"entity_types": ["person"]},
        )
        assert resp.status_code == 200
        # Will quickly fail because no documents, but the endpoint responds
        assert resp.json()["status"] == "running"

    def test_discover_entity_types(self, client: TestClient):
        """Mock the LLM call to test the endpoint wiring."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"choices":[{"message":{"content":"person, organization, location"}}]}'
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = lambda *a: None

        with patch("app.services.indexing_service.urllib.request.urlopen", return_value=mock_resp):
            resp = client.post(
                "/api/datasets/ds/discover-entity-types",
                json={"sample_text": "John works at Acme Corp in New York." * 3},
            )
            assert resp.status_code == 200
            types = resp.json()["entity_types"]
            assert "person" in types
            assert "organization" in types


class TestSearchRouter:
    def test_search_invalid_mode(self, client: TestClient, dataset_dir):
        resp = client.post(
            "/api/datasets/test_ds/search",
            json={"query": "test", "mode": "badmode"},
        )
        assert resp.status_code == 422  # Pydantic validation

    def test_search_missing_dataset(self, client: TestClient):
        resp = client.post(
            "/api/datasets/nope/search",
            json={"query": "test"},
        )
        assert resp.status_code == 404

    def test_search_success(self, client: TestClient, dataset_dir):
        mock_rag = AsyncMock()
        mock_rag.aquery = AsyncMock(return_value="Answer is 42.")
        with patch("app.services.search_service.get_rag", return_value=mock_rag):
            resp = client.post(
                "/api/datasets/test_ds/search",
                json={"query": "what?", "mode": "mix"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["answer"] == "Answer is 42."
            assert data["mode"] == "mix"


class TestGraphRouter:
    def test_graph_stats_missing_dataset(self, client: TestClient):
        resp = client.get("/api/datasets/nope/graph/stats")
        assert resp.status_code == 404

    def test_entities_missing_dataset(self, client: TestClient):
        resp = client.get("/api/datasets/nope/entities")
        assert resp.status_code == 404

    def test_relationships_missing_dataset(self, client: TestClient):
        resp = client.get("/api/datasets/nope/relationships")
        assert resp.status_code == 404
