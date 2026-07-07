"""图谱查询、统计、实体/关系分页接口测试。

覆盖:
    GET /api/datasets/{id}/graph
    GET /api/datasets/{id}/graph/stats
    GET /api/datasets/{id}/entities
    GET /api/datasets/{id}/relationships

依赖 conftest 的 indexed_dataset fixture（需存在已完成索引的数据集）。
"""

from __future__ import annotations

import pytest
import requests


class TestGraph:
    def test_get_graph_data(self, api, indexed_dataset):
        """应返回 nodes 和 edges。"""
        r = requests.get(f"{api}/datasets/{indexed_dataset}/graph", params={"limit": 50})
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data["nodes"], list)
        assert isinstance(data["edges"], list)

    def test_get_graph_data_with_limit(self, api, indexed_dataset):
        """应遵守 limit 参数。"""
        r = requests.get(f"{api}/datasets/{indexed_dataset}/graph", params={"limit": 5})
        assert r.status_code == 200
        assert len(r.json()["nodes"]) <= 5

    def test_get_graph_data_with_type_filter(self, api, indexed_dataset):
        """应支持按实体类型过滤。"""
        r = requests.get(f"{api}/datasets/{indexed_dataset}/graph", params={"limit": 50})
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
            for n in r.json()["nodes"]:
                assert n.get("type") == types[0]

    def test_get_graph_stats(self, api, indexed_dataset):
        """应返回实体数与关系数（LightRAG 无社区概念，故不含 community_count）。"""
        r = requests.get(f"{api}/datasets/{indexed_dataset}/graph/stats")
        assert r.status_code == 200
        stats = r.json()
        assert isinstance(stats["entity_count"], int)
        assert isinstance(stats["relationship_count"], int)
        assert isinstance(stats["entity_types"], dict)

    def test_list_entities(self, api, indexed_dataset):
        """实体分页项应含 title / type 字段。"""
        r = requests.get(
            f"{api}/datasets/{indexed_dataset}/entities",
            params={"page": 1, "page_size": 10},
        )
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data["items"], list)
        assert data["page"] == 1
        assert data["page_size"] == 10
        if data["items"]:
            entity = data["items"][0]
            assert "title" in entity
            assert "type" in entity

    def test_list_entities_pagination(self, api, indexed_dataset):
        """分页应正确工作。"""
        r = requests.get(
            f"{api}/datasets/{indexed_dataset}/entities",
            params={"page": 1, "page_size": 3},
        )
        assert r.status_code == 200
        data = r.json()
        if data["total"] > 3:
            assert len(data["items"]) == 3
            r2 = requests.get(
                f"{api}/datasets/{indexed_dataset}/entities",
                params={"page": 2, "page_size": 3},
            )
            assert r2.status_code == 200
            assert len(r2.json()["items"]) > 0

    def test_list_relationships(self, api, indexed_dataset):
        """关系分页项应含 source / target 字段。"""
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
        """不存在的数据集应返回 404。"""
        r = requests.get(f"{api}/datasets/nonexistent_id/graph")
        assert r.status_code == 404

    def test_graph_stats_nonexistent_dataset(self, api):
        """统计接口对不存在的数据集应返回 404。"""
        r = requests.get(f"{api}/datasets/nonexistent_id/graph/stats")
        assert r.status_code == 404
