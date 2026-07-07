"""数据集 CRUD 接口测试。

覆盖:
    GET    /api/datasets
    POST   /api/datasets
    GET    /api/datasets/{id}
    DELETE /api/datasets/{id}
"""

from __future__ import annotations

import requests


class TestDatasets:
    def test_list_datasets(self, api):
        r = requests.get(f"{api}/datasets")
        assert r.status_code == 200
        data = r.json()
        assert "datasets" in data
        assert isinstance(data["datasets"], list)

    def test_create_and_delete_dataset(self, api):
        # 创建
        r = requests.post(f"{api}/datasets", json={"name": "test_crud"})
        assert r.status_code == 201
        ds = r.json()
        assert ds["name"] == "test_crud"
        ds_id = ds["id"]

        # 查询
        r = requests.get(f"{api}/datasets/{ds_id}")
        assert r.status_code == 200
        assert r.json()["id"] == ds_id

        # 删除
        r = requests.delete(f"{api}/datasets/{ds_id}")
        assert r.status_code == 200

        # 确认已删除
        r = requests.get(f"{api}/datasets/{ds_id}")
        assert r.status_code == 404
