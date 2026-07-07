"""纯检索接口测试（不生成答案）。

覆盖:
    POST /api/datasets/{id}/search/context

只返回命中的上下文（实体/关系/文本块），不调用 LLM。
依赖 conftest 的 indexed_dataset fixture。
"""

from __future__ import annotations

import requests


class TestSearchContext:
    def test_context_invalid_mode(self, api, indexed_dataset):
        """非法的 mode 会被 Pydantic pattern 校验拦下，返回 422。"""
        r = requests.post(
            f"{api}/datasets/{indexed_dataset}/search/context",
            json={"query": "test", "mode": "invalid_mode"},
        )
        assert r.status_code == 422

    def test_context_nonexistent_dataset(self, api):
        """对不存在的数据集检索应返回 404。"""
        r = requests.post(
            f"{api}/datasets/nonexistent_id/search/context",
            json={"query": "test", "mode": "local"},
        )
        assert r.status_code == 404

    def test_context_basic_alias(self, api, indexed_dataset):
        """basic 是 naive 的别名，响应里会归一化为 naive。"""
        r = requests.post(
            f"{api}/datasets/{indexed_dataset}/search/context",
            json={"query": "什么是知识图谱？", "mode": "basic"},
            timeout=120,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["mode"] == "naive"
        assert "context" in data
        assert isinstance(data["context"], str)

    def test_context_mix_mode(self, api, indexed_dataset):
        """默认混合检索应返回非空上下文，且不含答案字段。"""
        r = requests.post(
            f"{api}/datasets/{indexed_dataset}/search/context",
            json={"query": "概述主要内容", "mode": "mix"},
            timeout=120,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["mode"] == "mix"
        assert data["query"] == "概述主要内容"
        assert isinstance(data["context"], str)
        assert len(data["context"]) > 0
        assert "answer" not in data
