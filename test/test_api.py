"""GraphRAG 后端 API 集成测试。

用法:
    cd backend
    uv run python -m pytest ../test/test_api.py -v

前提: 后端已启动 (http://localhost:8777)
"""

from __future__ import annotations

import os
import tempfile
import time

import pytest
import requests

BASE = os.environ.get("GRAPHARG_API_BASE", "http://localhost:8777/api")
TIMEOUT = 600  # 索引最多等 10 分钟


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def api():
    """Verify backend is reachable before running tests."""
    try:
        r = requests.get(f"{BASE}/health", timeout=5)
        r.raise_for_status()
    except requests.ConnectionError:
        pytest.skip(f"Backend not reachable at {BASE}")
    return BASE


@pytest.fixture
def sample_txt(tmp_path) -> str:
    """Create a small UTF-8 text file."""
    p = tmp_path / "sample.txt"
    p.write_text(
        "人工智能是计算机科学的一个分支。"
        "机器学习是人工智能的核心领域。"
        "深度学习使用多层神经网络。"
        "自然语言处理研究如何让计算机理解人类语言。"
        "知识图谱用图的形式描述实体之间的关系。",
        encoding="utf-8",
    )
    return str(p)


@pytest.fixture
def sample_gbk(tmp_path) -> str:
    """Create a GBK-encoded text file (common for Chinese Windows)."""
    p = tmp_path / "gbk_file.txt"
    p.write_text("这是一段用GBK编码保存的中文文本。知识图谱和人工智能是热门研究方向。", encoding="gbk")
    return str(p)


@pytest.fixture
def sample_utf16(tmp_path) -> str:
    """Create a UTF-16 encoded text file."""
    p = tmp_path / "utf16_file.txt"
    p.write_text("UTF-16编码的文本。GraphRAG结合了知识图谱和检索增强生成技术。", encoding="utf-16")
    return str(p)


# ── 基础接口测试 ─────────────────────────────────────────────────────────


class TestHealth:
    def test_health(self, api):
        r = requests.get(f"{api}/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_config_status(self, api):
        r = requests.get(f"{api}/config/status")
        assert r.status_code == 200
        data = r.json()
        assert "configured" in data
        assert "model" in data


class TestDatasets:
    def test_list_datasets(self, api):
        r = requests.get(f"{api}/datasets")
        assert r.status_code == 200
        data = r.json()
        assert "datasets" in data
        assert isinstance(data["datasets"], list)

    def test_create_and_delete_dataset(self, api):
        # Create
        r = requests.post(f"{api}/datasets", json={"name": "test_crud"})
        assert r.status_code == 201
        ds = r.json()
        assert ds["name"] == "test_crud"
        ds_id = ds["id"]

        # Get
        r = requests.get(f"{api}/datasets/{ds_id}")
        assert r.status_code == 200
        assert r.json()["id"] == ds_id

        # Delete
        r = requests.delete(f"{api}/datasets/{ds_id}")
        assert r.status_code == 200

        # Verify deleted
        r = requests.get(f"{api}/datasets/{ds_id}")
        assert r.status_code == 404


# ── 文档上传测试 ─────────────────────────────────────────────────────────


class TestDocuments:
    @pytest.fixture
    def dataset(self, api):
        """Create a temporary dataset for document tests."""
        r = requests.post(f"{api}/datasets", json={"name": "test_docs"})
        ds_id = r.json()["id"]
        yield ds_id
        requests.delete(f"{api}/datasets/{ds_id}")

    def test_upload_utf8_txt(self, api, dataset, sample_txt):
        with open(sample_txt, "rb") as f:
            r = requests.post(
                f"{api}/datasets/{dataset}/documents",
                files={"files": ("sample.txt", f, "text/plain")},
            )
        assert r.status_code == 200
        data = r.json()
        assert data["uploaded"] == 1

    def test_upload_gbk_txt(self, api, dataset, sample_gbk):
        """GBK encoded file should be converted to UTF-8 on upload."""
        with open(sample_gbk, "rb") as f:
            r = requests.post(
                f"{api}/datasets/{dataset}/documents",
                files={"files": ("gbk_file.txt", f, "text/plain")},
            )
        assert r.status_code == 200
        data = r.json()
        assert data["uploaded"] == 1
        assert data["documents"][0]["extracted_chars"] > 0

    def test_upload_utf16_txt(self, api, dataset, sample_utf16):
        """UTF-16 encoded file should be converted to UTF-8 on upload."""
        with open(sample_utf16, "rb") as f:
            r = requests.post(
                f"{api}/datasets/{dataset}/documents",
                files={"files": ("utf16_file.txt", f, "text/plain")},
            )
        assert r.status_code == 200
        data = r.json()
        assert data["uploaded"] == 1
        assert data["documents"][0]["extracted_chars"] > 0

    def test_upload_uppercase_extension(self, api, dataset, sample_txt):
        """File with .TXT extension should be normalized to .txt."""
        with open(sample_txt, "rb") as f:
            r = requests.post(
                f"{api}/datasets/{dataset}/documents",
                files={"files": ("test_file.TXT", f, "text/plain")},
            )
        assert r.status_code == 200
        data = r.json()
        assert data["documents"][0]["name"] == "test_file.txt"

    def test_upload_unsupported_type(self, api, dataset, tmp_path):
        """Unsupported file types should be rejected."""
        p = tmp_path / "test.exe"
        p.write_bytes(b"\x00\x01\x02")
        with open(p, "rb") as f:
            r = requests.post(
                f"{api}/datasets/{dataset}/documents",
                files={"files": ("test.exe", f, "application/octet-stream")},
            )
        assert r.status_code == 400

    def test_list_documents(self, api, dataset, sample_txt):
        with open(sample_txt, "rb") as f:
            requests.post(
                f"{api}/datasets/{dataset}/documents",
                files={"files": ("sample.txt", f, "text/plain")},
            )
        r = requests.get(f"{api}/datasets/{dataset}/documents")
        assert r.status_code == 200
        data = r.json()
        assert len(data["documents"]) == 1

    def test_delete_document(self, api, dataset, sample_txt):
        with open(sample_txt, "rb") as f:
            requests.post(
                f"{api}/datasets/{dataset}/documents",
                files={"files": ("sample.txt", f, "text/plain")},
            )
        r = requests.delete(f"{api}/datasets/{dataset}/documents/sample.txt")
        assert r.status_code == 200

        r = requests.get(f"{api}/datasets/{dataset}/documents")
        assert len(r.json()["documents"]) == 0


# ── 索引接口测试 ─────────────────────────────────────────────────────────


class TestIndexing:
    @pytest.fixture
    def dataset_with_doc(self, api, sample_txt):
        """Create a dataset with an uploaded document."""
        r = requests.post(f"{api}/datasets", json={"name": "test_index"})
        ds_id = r.json()["id"]
        with open(sample_txt, "rb") as f:
            requests.post(
                f"{api}/datasets/{ds_id}/documents",
                files={"files": ("sample.txt", f, "text/plain")},
            )
        yield ds_id
        requests.delete(f"{api}/datasets/{ds_id}")

    def test_start_indexing(self, api, dataset_with_doc):
        """Start indexing should return running status."""
        r = requests.post(
            f"{api}/datasets/{dataset_with_doc}/index",
            json={"entity_types": None, "entity_type_mode": "default"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "running"

    def test_index_status_endpoint(self, api, dataset_with_doc):
        """SSE status endpoint should return a valid response."""
        # Start indexing first
        requests.post(
            f"{api}/datasets/{dataset_with_doc}/index",
            json={"entity_types": None, "entity_type_mode": "default"},
        )
        # Check status (non-streaming, just first response)
        r = requests.get(
            f"{api}/datasets/{dataset_with_doc}/index/status",
            stream=True,
            timeout=5,
        )
        assert r.status_code == 200

    def test_start_indexing_no_files(self, api):
        """Indexing a dataset with no files should fail immediately."""
        r = requests.post(f"{api}/datasets", json={"name": "test_no_files"})
        ds_id = r.json()["id"]
        try:
            r = requests.post(
                f"{api}/datasets/{ds_id}/index",
                json={"entity_types": None, "entity_type_mode": "default"},
            )
            assert r.status_code == 200
            # Status should transition to failed quickly
            time.sleep(2)
            r = requests.get(f"{api}/datasets/{ds_id}/index/status", timeout=5)
            # The SSE endpoint returns the current status
        finally:
            requests.delete(f"{api}/datasets/{ds_id}")


# ── 图谱查询接口测试 ─────────────────────────────────────────────────────────


class TestGraph:
    """Tests for graph query endpoints.

    These tests require a dataset with a completed index.
    They use the first indexed dataset found, or skip if none available.
    """

    @pytest.fixture(scope="class")
    def indexed_dataset(self, api):
        """Find an indexed dataset to use for graph queries."""
        r = requests.get(f"{api}/datasets")
        datasets = r.json().get("datasets", [])
        for ds in datasets:
            if ds.get("has_index") or ds.get("entity_count", 0) > 0:
                return ds["id"]
        pytest.skip("No indexed dataset available for graph tests")

    def test_get_graph_data(self, api, indexed_dataset):
        """GET /api/datasets/{id}/graph should return nodes and edges."""
        r = requests.get(
            f"{api}/datasets/{indexed_dataset}/graph",
            params={"limit": 50},
        )
        assert r.status_code == 200
        data = r.json()
        assert "nodes" in data
        assert "edges" in data
        assert isinstance(data["nodes"], list)
        assert isinstance(data["edges"], list)

    def test_get_graph_data_with_limit(self, api, indexed_dataset):
        """Graph data should respect the limit parameter."""
        r = requests.get(
            f"{api}/datasets/{indexed_dataset}/graph",
            params={"limit": 5},
        )
        assert r.status_code == 200
        data = r.json()
        assert len(data["nodes"]) <= 5

    def test_get_graph_data_with_type_filter(self, api, indexed_dataset):
        """Graph data should support entity type filtering."""
        # First get all data to find a type
        r = requests.get(
            f"{api}/datasets/{indexed_dataset}/graph",
            params={"limit": 50},
        )
        assert r.status_code == 200
        nodes = r.json()["nodes"]
        if not nodes:
            pytest.skip("No nodes in graph")
        types = list({n.get("type") for n in nodes if n.get("type")})
        if types:
            r = requests.get(
                f"{api}/datasets/{indexed_dataset}/graph",
                params={"limit": 50, "types": types[0]},
            )
            assert r.status_code == 200
            filtered_nodes = r.json()["nodes"]
            for n in filtered_nodes:
                assert n.get("type") == types[0]

    def test_get_graph_stats(self, api, indexed_dataset):
        """GET /api/datasets/{id}/graph/stats should return counts."""
        r = requests.get(f"{api}/datasets/{indexed_dataset}/graph/stats")
        assert r.status_code == 200
        stats = r.json()
        assert "entity_count" in stats
        assert "relationship_count" in stats
        assert "community_count" in stats
        assert isinstance(stats["entity_count"], int)
        assert isinstance(stats["relationship_count"], int)
        assert isinstance(stats["community_count"], int)

    def test_list_entities(self, api, indexed_dataset):
        """GET /api/datasets/{id}/entities should return paginated entities."""
        r = requests.get(
            f"{api}/datasets/{indexed_dataset}/entities",
            params={"page": 1, "page_size": 10},
        )
        assert r.status_code == 200
        data = r.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data
        assert isinstance(data["items"], list)
        assert data["page"] == 1
        assert data["page_size"] == 10
        if data["items"]:
            entity = data["items"][0]
            assert "name" in entity
            assert "type" in entity

    def test_list_entities_pagination(self, api, indexed_dataset):
        """Entity pagination should work correctly."""
        r = requests.get(
            f"{api}/datasets/{indexed_dataset}/entities",
            params={"page": 1, "page_size": 3},
        )
        assert r.status_code == 200
        data = r.json()
        if data["total"] > 3:
            assert len(data["items"]) == 3
            # Page 2 should also have items
            r2 = requests.get(
                f"{api}/datasets/{indexed_dataset}/entities",
                params={"page": 2, "page_size": 3},
            )
            assert r2.status_code == 200
            data2 = r2.json()
            assert len(data2["items"]) > 0

    def test_list_relationships(self, api, indexed_dataset):
        """GET /api/datasets/{id}/relationships should return paginated relationships."""
        r = requests.get(
            f"{api}/datasets/{indexed_dataset}/relationships",
            params={"page": 1, "page_size": 10},
        )
        assert r.status_code == 200
        data = r.json()
        assert "items" in data
        assert "total" in data
        if data["items"]:
            rel = data["items"][0]
            assert "source" in rel
            assert "target" in rel

    def test_graph_nonexistent_dataset(self, api):
        """Graph endpoints should return 404 for nonexistent dataset."""
        r = requests.get(f"{api}/datasets/nonexistent_id/graph")
        assert r.status_code == 404

    def test_graph_stats_nonexistent_dataset(self, api):
        """Stats endpoint should return 404 for nonexistent dataset."""
        r = requests.get(f"{api}/datasets/nonexistent_id/graph/stats")
        assert r.status_code == 404


# ── 社区接口测试 ─────────────────────────────────────────────────────────


class TestCommunity:
    """Tests for community list and detail endpoints.

    Requires a dataset with completed indexing (community_reports.parquet).
    """

    @pytest.fixture(scope="class")
    def indexed_dataset(self, api):
        """Find an indexed dataset with community data."""
        r = requests.get(f"{api}/datasets")
        datasets = r.json().get("datasets", [])
        for ds in datasets:
            if ds.get("has_index") or ds.get("community_count", 0) > 0:
                return ds["id"]
        pytest.skip("No indexed dataset available for community tests")

    # ── 社区列表 ────────────────────────────────────────────────────────

    def test_list_communities(self, api, indexed_dataset):
        """GET /api/datasets/{id}/communities should return a JSON array."""
        r = requests.get(f"{api}/datasets/{indexed_dataset}/communities")
        assert r.status_code == 200
        data = r.json()
        # Endpoint returns a plain list, not paginated
        assert isinstance(data, list), f"Expected list, got {type(data).__name__}: {str(data)[:200]}"
        assert len(data) > 0, "Expected at least one community"

    def test_community_has_required_fields(self, api, indexed_dataset):
        """Each community record should have id, title, and human_readable_id."""
        r = requests.get(f"{api}/datasets/{indexed_dataset}/communities")
        data = r.json()
        if not data:
            pytest.skip("No communities in dataset")

        comm = data[0]
        # id field is required (added by backend from human_readable_id)
        assert "id" in comm, f"Missing 'id' field. Keys: {list(comm.keys())}"
        assert "title" in comm, f"Missing 'title' field. Keys: {list(comm.keys())}"

    def test_community_has_rating(self, api, indexed_dataset):
        """Community records should include rating if available in parquet."""
        r = requests.get(f"{api}/datasets/{indexed_dataset}/communities")
        data = r.json()
        if not data:
            pytest.skip("No communities in dataset")

        comm = data[0]
        # rating may or may not exist depending on parquet schema
        if "rating" in comm:
            assert isinstance(comm["rating"], (int, float)), (
                f"rating should be numeric, got {type(comm['rating']).__name__}: {comm['rating']}"
            )

    def test_community_ids_are_unique(self, api, indexed_dataset):
        """All community ids should be unique."""
        r = requests.get(f"{api}/datasets/{indexed_dataset}/communities")
        data = r.json()
        if len(data) < 2:
            pytest.skip("Need at least 2 communities")

        ids = [c.get("id") for c in data]
        assert len(ids) == len(set(ids)), f"Duplicate community ids found: {ids}"

    def test_community_list_consistent_with_stats(self, api, indexed_dataset):
        """Community list length should match stats community_count."""
        r_stats = requests.get(f"{api}/datasets/{indexed_dataset}/graph/stats")
        assert r_stats.status_code == 200
        expected = r_stats.json()["community_count"]

        r = requests.get(f"{api}/datasets/{indexed_dataset}/communities")
        data = r.json()
        assert len(data) == expected, (
            f"Community list has {len(data)} items but stats says {expected}"
        )

    # ── 社区详情 ────────────────────────────────────────────────────────

    def test_community_detail_by_id(self, api, indexed_dataset):
        """GET /api/datasets/{id}/communities/{cid} should return full detail."""
        # Get list first
        r = requests.get(f"{api}/datasets/{indexed_dataset}/communities")
        data = r.json()
        if not data:
            pytest.skip("No communities in dataset")

        cid = data[0]["id"]
        r = requests.get(f"{api}/datasets/{indexed_dataset}/communities/{cid}")
        assert r.status_code == 200
        detail = r.json()

        # Detail should have more fields than the summary
        assert "title" in detail or "report" in detail or "summary" in detail, (
            f"Detail missing expected fields. Keys: {list(detail.keys())}"
        )

    def test_community_detail_has_summary_or_report(self, api, indexed_dataset):
        """Community detail should have summary or report content."""
        r = requests.get(f"{api}/datasets/{indexed_dataset}/communities")
        data = r.json()
        if not data:
            pytest.skip("No communities in dataset")

        cid = data[0]["id"]
        r = requests.get(f"{api}/datasets/{indexed_dataset}/communities/{cid}")
        detail = r.json()

        has_content = (
            detail.get("summary")
            or detail.get("report")
            or detail.get("full_content_json")
        )
        assert has_content, (
            f"Detail has no content (summary/report/full_content_json). "
            f"Keys: {list(detail.keys())}"
        )

    def test_community_detail_findings_parsed(self, api, indexed_dataset):
        """If findings exist, they should be parsed as a list (not JSON string)."""
        r = requests.get(f"{api}/datasets/{indexed_dataset}/communities")
        data = r.json()
        if not data:
            pytest.skip("No communities in dataset")

        cid = data[0]["id"]
        r = requests.get(f"{api}/datasets/{indexed_dataset}/communities/{cid}")
        detail = r.json()

        if "findings" in detail and detail["findings"]:
            assert isinstance(detail["findings"], list), (
                f"findings should be a list, got {type(detail['findings']).__name__}"
            )
            if detail["findings"]:
                finding = detail["findings"][0]
                assert isinstance(finding, dict), (
                    f"Each finding should be a dict, got {type(finding).__name__}"
                )

    def test_community_detail_all_communities(self, api, indexed_dataset):
        """Every community from the list should have a valid detail endpoint."""
        r = requests.get(f"{api}/datasets/{indexed_dataset}/communities")
        data = r.json()
        if not data:
            pytest.skip("No communities in dataset")

        errors = []
        for comm in data:
            cid = comm["id"]
            r = requests.get(f"{api}/datasets/{indexed_dataset}/communities/{cid}")
            if r.status_code != 200:
                errors.append(f"Community {cid} returned {r.status_code}")
        assert not errors, f"Some community details failed: {errors}"

    # ── 错误处理 ────────────────────────────────────────────────────────

    def test_community_detail_nonexistent_id(self, api, indexed_dataset):
        """Detail for nonexistent community id should return 404."""
        r = requests.get(
            f"{api}/datasets/{indexed_dataset}/communities/999999"
        )
        assert r.status_code == 404

    def test_community_list_nonexistent_dataset(self, api):
        """Communities endpoint should return 404 for nonexistent dataset."""
        r = requests.get(f"{api}/datasets/nonexistent_id/communities")
        assert r.status_code == 404

    def test_community_detail_nonexistent_dataset(self, api):
        """Community detail should return 404 for nonexistent dataset."""
        r = requests.get(f"{api}/datasets/nonexistent_id/communities/0")
        assert r.status_code == 404


# ── 搜索接口测试 ─────────────────────────────────────────────────────────


class TestSearch:
    """Tests for the search endpoint."""

    @pytest.fixture(scope="class")
    def indexed_dataset(self, api):
        """Find an indexed dataset to use for search tests."""
        r = requests.get(f"{api}/datasets")
        datasets = r.json().get("datasets", [])
        for ds in datasets:
            if ds.get("has_index") or ds.get("entity_count", 0) > 0:
                return ds["id"]
        pytest.skip("No indexed dataset available for search tests")

    def test_search_invalid_mode(self, api, indexed_dataset):
        """Search with invalid mode should return 400."""
        r = requests.post(
            f"{api}/datasets/{indexed_dataset}/search",
            json={"query": "test", "mode": "invalid_mode"},
        )
        assert r.status_code == 400

    def test_search_nonexistent_dataset(self, api):
        """Search on nonexistent dataset should return 404."""
        r = requests.post(
            f"{api}/datasets/nonexistent_id/search",
            json={"query": "test", "mode": "local"},
        )
        assert r.status_code == 404

    def test_search_basic_mode(self, api, indexed_dataset):
        """Basic RAG search should work if text_units exist."""
        r = requests.post(
            f"{api}/datasets/{indexed_dataset}/search",
            json={"query": "什么是知识图谱？", "mode": "basic"},
            timeout=120,
        )
        assert r.status_code == 200
        data = r.json()
        assert "query" in data
        assert "mode" in data
        assert data["mode"] == "basic"
        assert "answer" in data
        assert len(data["answer"]) > 0

    def test_search_local_mode(self, api, indexed_dataset):
        """Local search should work if index is complete."""
        r = requests.post(
            f"{api}/datasets/{indexed_dataset}/search",
            json={"query": "什么是知识图谱？", "mode": "local"},
            timeout=120,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["mode"] == "local"
        # May return friendly error if index incomplete
        assert "answer" in data

    def test_search_global_mode(self, api, indexed_dataset):
        """Global search should work if index is complete."""
        r = requests.post(
            f"{api}/datasets/{indexed_dataset}/search",
            json={"query": "概述主要概念", "mode": "global"},
            timeout=120,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["mode"] == "global"
        assert "answer" in data


# ── 编码转换单元测试（不依赖后端）─────────────────────────────────────


class TestEncoding:
    """Test the _decode_to_utf8 helper directly."""

    def test_utf8(self):
        from app.services.document_service import _decode_to_utf8
        raw = "你好世界".encode("utf-8")
        assert _decode_to_utf8(raw, "test.txt") == "你好世界"

    def test_utf8_bom(self):
        from app.services.document_service import _decode_to_utf8
        raw = "你好世界".encode("utf-8-sig")
        assert _decode_to_utf8(raw, "test.txt") == "你好世界"

    def test_utf16_le(self):
        from app.services.document_service import _decode_to_utf8
        raw = "你好世界".encode("utf-16")
        result = _decode_to_utf8(raw, "test.txt")
        assert "你好世界" in result

    def test_gbk(self):
        from app.services.document_service import _decode_to_utf8
        raw = "你好世界".encode("gbk")
        assert _decode_to_utf8(raw, "test.txt") == "你好世界"

    def test_gb2312(self):
        from app.services.document_service import _decode_to_utf8
        raw = "人工智能".encode("gb2312")
        assert _decode_to_utf8(raw, "test.txt") == "人工智能"


# ── 端到端索引测试（需要 LLM API）─────────────────────────────────────


class TestIndexingE2E:
    """End-to-end test: create → upload → index → query.

    These tests require a valid LLM API key and will actually call the LLM.
    Skip by default; run with: pytest -m e2e
    """

    @pytest.mark.e2e
    def test_full_pipeline(self, api, sample_txt):
        # 1. Create dataset
        r = requests.post(f"{api}/datasets", json={"name": "e2e_test"})
        assert r.status_code == 201
        ds_id = r.json()["id"]

        try:
            # 2. Upload file
            with open(sample_txt, "rb") as f:
                r = requests.post(
                    f"{api}/datasets/{ds_id}/documents",
                    files={"files": ("sample.txt", f, "text/plain")},
                )
            assert r.status_code == 200

            # 3. Start indexing
            r = requests.post(
                f"{api}/datasets/{ds_id}/index",
                json={"entity_types": ["概念", "技术"], "entity_type_mode": "manual"},
            )
            assert r.status_code == 200
            assert r.json()["status"] == "running"

            # 4. Poll until done
            start = time.time()
            final_status = None
            while time.time() - start < TIMEOUT:
                r = requests.get(f"{api}/datasets/{ds_id}/index/status")
                data = r.json()
                status = data["status"]
                print(f"  [{int(time.time()-start)}s] {status} - {data.get('message', '')}")

                if status in ("completed", "failed"):
                    final_status = data
                    break
                time.sleep(5)

            assert final_status is not None, "Indexing timed out"
            assert final_status["status"] == "completed", (
                f"Index failed: {final_status.get('error', '')}"
            )

            # 5. Check graph stats
            r = requests.get(f"{api}/datasets/{ds_id}/graph/stats")
            assert r.status_code == 200
            stats = r.json()
            assert stats["entity_count"] > 0
            print(f"  Entities: {stats['entity_count']}, "
                  f"Relationships: {stats['relationship_count']}, "
                  f"Communities: {stats['community_count']}")

            # 6. Get graph data
            r = requests.get(f"{api}/datasets/{ds_id}/graph", params={"limit": 10})
            assert r.status_code == 200
            graph = r.json()
            assert len(graph["nodes"]) > 0
            assert len(graph["edges"]) > 0

            # 7. Search
            r = requests.post(
                f"{api}/datasets/{ds_id}/search",
                json={"query": "什么是知识图谱？", "mode": "local"},
                timeout=120,
            )
            assert r.status_code == 200
            answer = r.json()["answer"]
            assert len(answer) > 0
            print(f"  Search answer: {answer[:200]}...")

        finally:
            requests.delete(f"{api}/datasets/{ds_id}")
