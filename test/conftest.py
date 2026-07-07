"""GraphMind 后端 API 测试的共享 pytest fixtures。

用法:
    cd backend
    uv run python -m pytest ../test -v              # 全部
    uv run python -m pytest ../test/test_graph.py -v  # 单个文件

前提:
    - 后端已启动 (http://localhost:8777)
    - 图谱 / 搜索类测试还需存在至少一个已完成索引的数据集

可用 GRAPHMIND_API_BASE 环境变量覆盖后端地址。
"""

from __future__ import annotations

import os

import pytest
import requests

BASE = os.environ.get("GRAPHMIND_API_BASE", "http://localhost:8777/api")


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "e2e: 端到端测试，会真实调用 LLM，默认跳过（用 -m e2e 运行）"
    )


@pytest.fixture(scope="session")
def api() -> str:
    """确认后端可达；不可达则跳过所有依赖它的测试。"""
    try:
        r = requests.get(f"{BASE}/health", timeout=5)
        r.raise_for_status()
    except requests.ConnectionError:
        pytest.skip(f"Backend not reachable at {BASE}")
    return BASE


@pytest.fixture(scope="session")
def indexed_dataset(api) -> str:
    """返回一个已完成索引的数据集 id；不存在则跳过。

    图谱、实体/关系、搜索类测试均依赖它——它们是只读的，复用现有数据集
    比每次重新索引（分钟级、耗 LLM 额度）更快。
    """
    r = requests.get(f"{api}/datasets")
    for ds in r.json().get("datasets", []):
        if ds.get("has_index") or ds.get("entity_count", 0) > 0:
            return ds["id"]
    pytest.skip("No indexed dataset available")


# ── 样本文档 fixtures（用于上传/编码测试）─────────────────────────────

@pytest.fixture
def sample_txt(tmp_path) -> str:
    """UTF-8 编码的小文本文件。"""
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
    """GBK 编码的中文文本文件（常见于中文 Windows）。"""
    p = tmp_path / "gbk_file.txt"
    p.write_text("这是一段用GBK编码保存的中文文本。知识图谱和人工智能是热门研究方向。", encoding="gbk")
    return str(p)


@pytest.fixture
def sample_utf16(tmp_path) -> str:
    """UTF-16 编码的文本文件。"""
    p = tmp_path / "utf16_file.txt"
    p.write_text("UTF-16编码的文本。GraphRAG结合了知识图谱和检索增强生成技术。", encoding="utf-16")
    return str(p)
