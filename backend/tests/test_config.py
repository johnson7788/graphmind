"""Tests for app.config."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch


class TestGetLlmConfig:
    def test_defaults_when_app_config_empty(self, monkeypatch):
        monkeypatch.setattr("app.config.APP_CONFIG", {})
        from app.config import get_llm_config
        cfg = get_llm_config()
        assert cfg["model"] == "gpt-4o"
        assert cfg["api_base"] == "https://api.openai.com/v1"
        assert cfg["emb_model"] == "text-embedding-3-small"
        assert cfg["emb_dim"] == 1024

    def test_reads_from_app_config(self, monkeypatch):
        monkeypatch.setattr("app.config.APP_CONFIG", {
            "llm": {"api_key": "sk-test", "model": "qwen-max", "api_base": "http://api"},
            "embedding": {"model": "text-emb-v3", "api_base": "http://emb", "dim": 768},
            "vision": {"model": "qwen-vl", "api_base": "http://vis"},
        })
        from app.config import get_llm_config
        cfg = get_llm_config()
        assert cfg["api_key"] == "sk-test"
        assert cfg["model"] == "qwen-max"
        assert cfg["emb_model"] == "text-emb-v3"
        assert cfg["emb_dim"] == 768
        assert cfg["vision_model"] == "qwen-vl"
        assert cfg["vision_base"] == "http://vis"

    def test_api_key_fallback_to_env(self, monkeypatch):
        monkeypatch.setattr("app.config.APP_CONFIG", {"llm": {}})
        monkeypatch.setenv("GRAPHRAG_API_KEY", "sk-env-key")
        from app.config import get_llm_config
        cfg = get_llm_config()
        assert cfg["api_key"] == "sk-env-key"

    def test_api_key_llm_api_key_env(self, monkeypatch):
        monkeypatch.setattr("app.config.APP_CONFIG", {"llm": {}})
        monkeypatch.delenv("GRAPHRAG_API_KEY", raising=False)
        monkeypatch.setenv("LLM_API_KEY", "sk-llm-key")
        from app.config import get_llm_config
        cfg = get_llm_config()
        assert cfg["api_key"] == "sk-llm-key"

    def test_vision_defaults_to_llm_model(self, monkeypatch):
        monkeypatch.setattr("app.config.APP_CONFIG", {
            "llm": {"model": "qwen-max"},
        })
        from app.config import get_llm_config
        cfg = get_llm_config()
        assert cfg["vision_model"] == "qwen-max"


class TestIsConfigValid:
    def test_valid_key(self, monkeypatch):
        monkeypatch.setattr("app.config.APP_CONFIG", {"llm": {"api_key": "sk-real-key"}})
        from app.config import is_config_valid
        assert is_config_valid() is True

    def test_empty_key(self, monkeypatch):
        monkeypatch.setattr("app.config.APP_CONFIG", {"llm": {"api_key": ""}})
        monkeypatch.delenv("GRAPHRAG_API_KEY", raising=False)
        monkeypatch.delenv("LLM_API_KEY", raising=False)
        from app.config import is_config_valid
        assert is_config_valid() is False

    def test_placeholder_key(self, monkeypatch):
        monkeypatch.setattr("app.config.APP_CONFIG", {"llm": {"api_key": "***"}})
        from app.config import is_config_valid
        assert is_config_valid() is False

    def test_template_placeholder(self, monkeypatch):
        monkeypatch.setattr("app.config.APP_CONFIG", {"llm": {"api_key": "sk-your-api-key-here"}})
        from app.config import is_config_valid
        assert is_config_valid() is False


class TestLoadAppConfig:
    def test_loads_local_yaml(self, tmp_path, monkeypatch):
        import yaml
        cfg_file = tmp_path / "config.local.yaml"
        cfg_file.write_text(yaml.dump({"llm": {"model": "test-model"}}))
        monkeypatch.setattr("app.config.BACKEND_DIR", tmp_path)
        from app.config import _load_app_config
        cfg = _load_app_config()
        assert cfg["llm"]["model"] == "test-model"

    def test_fallback_to_template(self, tmp_path, monkeypatch):
        import yaml
        cfg_file = tmp_path / "config.template.yaml"
        cfg_file.write_text(yaml.dump({"llm": {"model": "tmpl-model"}}))
        monkeypatch.setattr("app.config.BACKEND_DIR", tmp_path)
        from app.config import _load_app_config
        cfg = _load_app_config()
        assert cfg["llm"]["model"] == "tmpl-model"

    def test_local_preferred_over_template(self, tmp_path, monkeypatch):
        import yaml
        (tmp_path / "config.local.yaml").write_text(yaml.dump({"llm": {"model": "local"}}))
        (tmp_path / "config.template.yaml").write_text(yaml.dump({"llm": {"model": "template"}}))
        monkeypatch.setattr("app.config.BACKEND_DIR", tmp_path)
        from app.config import _load_app_config
        cfg = _load_app_config()
        assert cfg["llm"]["model"] == "local"

    def test_returns_empty_when_no_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr("app.config.BACKEND_DIR", tmp_path)
        monkeypatch.setattr("app.config.PROJECT_ROOT", tmp_path)
        from app.config import _load_app_config
        assert _load_app_config() == {}


class TestPaths:
    def test_data_root_is_directory(self):
        from app.config import DATA_ROOT
        assert DATA_ROOT.is_dir()

    def test_default_entity_types(self):
        from app.config import DEFAULT_ENTITY_TYPES
        assert "person" in DEFAULT_ENTITY_TYPES
        assert "organization" in DEFAULT_ENTITY_TYPES
        assert len(DEFAULT_ENTITY_TYPES) == 6
