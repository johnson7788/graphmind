"""单条关系精确查询接口测试。

覆盖:
    GET /api/datasets/{id}/relationship?source=&target=

按源/目标实体返回关系属性。
依赖 conftest 的 indexed_dataset fixture。
"""

from __future__ import annotations

import pytest
import requests


def _first_relationship(api: str, dataset_id: str) -> tuple[str, str]:
    """从关系分页列表取一对真实的 (source, target)；没有则跳过。"""
    r = requests.get(
        f"{api}/datasets/{dataset_id}/relationships", params={"page": 1, "page_size": 1}
    )
    r.raise_for_status()
    items = r.json().get("items", [])
    if not items:
        pytest.skip("No relationships in dataset")
    return items[0]["source"], items[0]["target"]


class TestRelationship:
    def test_relationship_detail(self, api, indexed_dataset):
        """应返回 source / target / properties。"""
        source, target = _first_relationship(api, indexed_dataset)
        r = requests.get(
            f"{api}/datasets/{indexed_dataset}/relationship",
            params={"source": source, "target": target},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["source"] == source
        assert data["target"] == target
        assert isinstance(data["properties"], dict)

    def test_relationship_not_found(self, api, indexed_dataset):
        """不存在的关系应返回 404。"""
        r = requests.get(
            f"{api}/datasets/{indexed_dataset}/relationship",
            params={"source": "__不存在_a__", "target": "__不存在_b__"},
        )
        assert r.status_code == 404

    def test_relationship_missing_params(self, api, indexed_dataset):
        """缺少 source/target 参数应返回 422。"""
        r = requests.get(f"{api}/datasets/{indexed_dataset}/relationship")
        assert r.status_code == 422

    def test_relationship_nonexistent_dataset(self, api):
        """不存在的数据集应返回 404。"""
        r = requests.get(
            f"{api}/datasets/nonexistent_id/relationship",
            params={"source": "a", "target": "b"},
        )
        assert r.status_code == 404
