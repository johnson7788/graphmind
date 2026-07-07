"""索引接口测试，以及创建→上传→索引→查询的端到端测试。

覆盖:
    POST /api/datasets/{id}/index
    GET  /api/datasets/{id}/index/status

端到端 (TestIndexingE2E) 会真实调用 LLM，默认跳过；运行:
    uv run python -m pytest ../test/test_indexing.py -m e2e -v
"""

from __future__ import annotations

import time

import pytest
import requests

TIMEOUT = 600  # 索引最多等 10 分钟


class TestIndexing:
    @pytest.fixture
    def dataset_with_doc(self, api, sample_txt):
        """创建一个已上传文档的数据集，用完即删。"""
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
        """启动索引应返回 running 状态。"""
        r = requests.post(
            f"{api}/datasets/{dataset_with_doc}/index",
            json={"entity_types": None, "entity_type_mode": "default"},
        )
        assert r.status_code == 200
        assert r.json()["status"] == "running"

    def test_index_status_endpoint(self, api, dataset_with_doc):
        """状态轮询接口应返回有效响应。"""
        requests.post(
            f"{api}/datasets/{dataset_with_doc}/index",
            json={"entity_types": None, "entity_type_mode": "default"},
        )
        r = requests.get(f"{api}/datasets/{dataset_with_doc}/index/status", timeout=5)
        assert r.status_code == 200
        assert "status" in r.json()

    def test_start_indexing_no_files(self, api):
        """对没有文档的数据集启动索引应很快失败。"""
        r = requests.post(f"{api}/datasets", json={"name": "test_no_files"})
        ds_id = r.json()["id"]
        try:
            r = requests.post(
                f"{api}/datasets/{ds_id}/index",
                json={"entity_types": None, "entity_type_mode": "default"},
            )
            assert r.status_code == 200
            time.sleep(2)
            r = requests.get(f"{api}/datasets/{ds_id}/index/status", timeout=5)
            assert r.status_code == 200
        finally:
            requests.delete(f"{api}/datasets/{ds_id}")


class TestIndexingE2E:
    """端到端: 创建 → 上传 → 索引 → 查询。需要有效的 LLM API Key，会实际调用 LLM。"""

    @pytest.mark.e2e
    def test_full_pipeline(self, api, sample_txt):
        # 1. 创建数据集
        r = requests.post(f"{api}/datasets", json={"name": "e2e_test"})
        assert r.status_code == 201
        ds_id = r.json()["id"]

        try:
            # 2. 上传文件
            with open(sample_txt, "rb") as f:
                r = requests.post(
                    f"{api}/datasets/{ds_id}/documents",
                    files={"files": ("sample.txt", f, "text/plain")},
                )
            assert r.status_code == 200

            # 3. 启动索引
            r = requests.post(
                f"{api}/datasets/{ds_id}/index",
                json={"entity_types": ["概念", "技术"], "entity_type_mode": "manual"},
            )
            assert r.status_code == 200
            assert r.json()["status"] == "running"

            # 4. 轮询直到完成
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

            # 5. 图谱统计
            r = requests.get(f"{api}/datasets/{ds_id}/graph/stats")
            assert r.status_code == 200
            stats = r.json()
            assert stats["entity_count"] > 0
            print(f"  Entities: {stats['entity_count']}, "
                  f"Relationships: {stats['relationship_count']}")

            # 6. 图谱数据
            r = requests.get(f"{api}/datasets/{ds_id}/graph", params={"limit": 10})
            assert r.status_code == 200
            graph = r.json()
            assert len(graph["nodes"]) > 0
            assert len(graph["edges"]) > 0

            # 7. 搜索
            r = requests.post(
                f"{api}/datasets/{ds_id}/search",
                json={"query": "什么是知识图谱？", "mode": "local"},
                timeout=120,
            )
            assert r.status_code == 200
            assert len(r.json()["answer"]) > 0

        finally:
            requests.delete(f"{api}/datasets/{ds_id}")
