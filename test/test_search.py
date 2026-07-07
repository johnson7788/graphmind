"""非流式问答接口测试。

覆盖:
    POST /api/datasets/{id}/search

流式 (SSE) 问答见 test_search_stream.py。
依赖 conftest 的 indexed_dataset fixture。
"""

from __future__ import annotations

import requests


class TestSearch:
    def test_search_invalid_mode(self, api, indexed_dataset):
        """非法的 mode 会被 Pydantic pattern 校验拦下，返回 422。"""
        r = requests.post(
            f"{api}/datasets/{indexed_dataset}/search",
            json={"query": "test", "mode": "invalid_mode"},
        )
        assert r.status_code == 422

    def test_search_nonexistent_dataset(self, api):
        """对不存在的数据集搜索应返回 404。"""
        r = requests.post(
            f"{api}/datasets/nonexistent_id/search",
            json={"query": "test", "mode": "local"},
        )
        assert r.status_code == 404

    def test_search_basic_mode(self, api, indexed_dataset):
        """基础 RAG：basic 是 naive 的别名，响应里会归一化为 naive。"""
        r = requests.post(
            f"{api}/datasets/{indexed_dataset}/search",
            json={"query": "什么是知识图谱？", "mode": "basic"},
            timeout=120,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["mode"] == "naive"
        assert len(data["answer"]) > 0

    def test_search_local_mode(self, api, indexed_dataset):
        r = requests.post(
            f"{api}/datasets/{indexed_dataset}/search",
            json={"query": "什么是知识图谱？", "mode": "local"},
            timeout=120,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["mode"] == "local"
        assert "answer" in data

    def test_search_global_mode(self, api, indexed_dataset):
        r = requests.post(
            f"{api}/datasets/{indexed_dataset}/search",
            json={"query": "概述主要概念", "mode": "global"},
            timeout=120,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["mode"] == "global"
        assert "answer" in data

    def test_search_mix_mode(self, api, indexed_dataset):
        """默认的混合检索（图谱+向量）应返回非空答案。"""
        r = requests.post(
            f"{api}/datasets/{indexed_dataset}/search",
            json={"query": "概述主要内容", "mode": "mix"},
            timeout=120,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["mode"] == "mix"
        assert "answer" in data
