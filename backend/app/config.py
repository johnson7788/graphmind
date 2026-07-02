"""Application configuration loader."""

from __future__ import annotations

import logging
import os
from pathlib import Path

import yaml

log = logging.getLogger("graphrag-backend")

# ── Paths ────────────────────────────────────────────────────────────────
BACKEND_DIR = Path(__file__).resolve().parent.parent  # backend/
PROJECT_ROOT = BACKEND_DIR.parent                     # demo_app/
DATA_ROOT = PROJECT_ROOT / "data"
DATA_ROOT.mkdir(parents=True, exist_ok=True)

# ── Default entity types ─────────────────────────────────────────────────
DEFAULT_ENTITY_TYPES = [
    "organization", "person", "location", "event", "concept", "technology",
]


def _load_app_config() -> dict:
    """Load LLM config: prefer config.local.yaml, fallback to config.template.yaml."""
    for name in ["config.local.yaml", "config.template.yaml"]:
        cfg_path = BACKEND_DIR / name
        if cfg_path.exists():
            with open(cfg_path) as f:
                cfg = yaml.safe_load(f) or {}
            log.info("Loaded config: %s", cfg_path)
            return cfg
    # Also check project root (legacy location)
    for name in ["config.local.yaml", "config.template.yaml"]:
        cfg_path = PROJECT_ROOT / name
        if cfg_path.exists():
            with open(cfg_path) as f:
                cfg = yaml.safe_load(f) or {}
            log.info("Loaded config from project root: %s", cfg_path)
            return cfg
    return {}


APP_CONFIG = _load_app_config()


def get_llm_config() -> dict:
    """Extract LLM / embedding / vision model configuration."""
    cfg = APP_CONFIG.get("llm", {})
    emb = APP_CONFIG.get("embedding", {})
    vis = APP_CONFIG.get("vision", {})
    api_key = cfg.get("api_key", "") or os.environ.get("GRAPHRAG_API_KEY", "") \
        or os.environ.get("LLM_API_KEY", "")
    api_base = cfg.get("api_base", "https://api.openai.com/v1")
    return {
        "api_key": api_key,
        "model": cfg.get("model", "gpt-4o"),
        "api_base": api_base,
        "emb_model": emb.get("model", "text-embedding-3-small"),
        "emb_base": emb.get("api_base", api_base),
        "emb_dim": int(emb.get("dim", 1024)),
        "vision_model": vis.get("model", cfg.get("model", "gpt-4o")),
        "vision_base": vis.get("api_base", api_base),
    }


def is_config_valid() -> bool:
    """Check if API key is configured."""
    llm = get_llm_config()
    return bool(llm["api_key"]) and llm["api_key"] not in ("***", "sk-your-api-key-here")
