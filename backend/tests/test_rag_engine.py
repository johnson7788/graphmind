"""Tests for app.services.rag_engine (helpers + factories)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from app.services.rag_engine import (
    dataset_root,
    rag_storage_dir,
    parse_output_dir,
    llm_config_language,
)
from app.config import DATA_ROOT


class TestPathHelpers:
    def test_dataset_root(self):
        assert dataset_root("myds") == DATA_ROOT / "myds"

    def test_rag_storage_dir(self):
        assert rag_storage_dir("myds") == DATA_ROOT / "myds" / "rag_storage"

    def test_parse_output_dir(self):
        assert parse_output_dir("myds") == DATA_ROOT / "myds" / "output"


class TestLlmConfigLanguage:
    def test_returns_none_when_not_set(self, monkeypatch):
        monkeypatch.setattr("app.config.APP_CONFIG", {})
        assert llm_config_language() is None

    def test_returns_language_from_config(self, monkeypatch):
        monkeypatch.setattr("app.config.APP_CONFIG", {
            "rag": {"language": "Simplified Chinese"},
        })
        assert llm_config_language() == "Simplified Chinese"

    def test_returns_none_when_empty_string(self, monkeypatch):
        monkeypatch.setattr("app.config.APP_CONFIG", {"rag": {"language": ""}})
        assert llm_config_language() is None

    def test_returns_none_when_rag_section_missing(self, monkeypatch):
        monkeypatch.setattr("app.config.APP_CONFIG", {"other": {}})
        assert llm_config_language() is None


class TestBuildEmbeddingFunc:
    def test_returns_embedding_func(self):
        from app.services.rag_engine import build_embedding_func
        from lightrag.utils import EmbeddingFunc
        llm = {
            "emb_dim": 768,
            "emb_model": "text-emb-v3",
            "api_key": "sk-test",
            "emb_base": "http://emb-api",
        }
        func = build_embedding_func(llm)
        assert isinstance(func, EmbeddingFunc)
        assert func.embedding_dim == 768


class TestMakeConfig:
    def test_config_fields(self):
        from app.services.rag_engine import _make_config
        cfg = _make_config("myds")
        assert "rag_storage" in cfg.working_dir
        assert cfg.parser == "mineru"
        assert cfg.parse_method == "auto"
        assert cfg.enable_image_processing is True
        assert cfg.enable_table_processing is True
        assert cfg.enable_equation_processing is True
