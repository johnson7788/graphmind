"""单个实体精确查询接口测试。

覆盖:
    GET /api/datasets/{id}/entity?name=

按名称返回实体节点属性 + 邻接实体名。
依赖 conftest 的 indexed_dataset fixture。
"""

from __future__ import annotations

import pytest
import requests


def _first_entity_name(api: str, dataset_id: str) -> str:
    """从实体分页列表取一个真实的实体名；没有则跳过。"""
    r = requests.get(
        f"{api}/datasets/{dataset_id}/entities", params={"page": 1, "page_size": 1}
    )
    r.raise_for_status()
    items = r.json().get("items", [])
    if not items:
        pytest.skip("No entities in dataset")
    return items[0]["title"]


class TestEntity:
    def test_entity_detail(self, api, indexed_dataset):
        """应返回 name / properties / neighbors。"""
        name = _first_entity_name(api, indexed_dataset)
        r = requests.get(
            f"{api}/datasets/{indexed_dataset}/entity", params={"name": name}
        )
        assert r.status_code == 200
        data = r.json()
        assert data["name"] == name
        assert isinstance(data["properties"], dict)
        assert "entity_type" in data["properties"]
        assert isinstance(data["neighbors"], list)

    def test_entity_not_found(self, api, indexed_dataset):
        """不存在的实体名应返回 404。"""
        r = requests.get(
            f"{api}/datasets/{indexed_dataset}/entity",
            params={"name": "__不存在的实体_xyz__"},
        )
        assert r.status_code == 404

    def test_entity_missing_name(self, api, indexed_dataset):
        """缺少 name 参数应返回 422。"""
        r = requests.get(f"{api}/datasets/{indexed_dataset}/entity")
        assert r.status_code == 422

    def test_entity_nonexistent_dataset(self, api):
        """不存在的数据集应返回 404。"""
        r = requests.get(
            f"{api}/datasets/nonexistent_id/entity", params={"name": "x"}
        )
        assert r.status_code == 404
