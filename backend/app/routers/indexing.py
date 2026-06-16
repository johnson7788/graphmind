"""Indexing, entity-type discovery, and config-check routes."""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter

from app.config import get_llm_config, is_config_valid
from app.models.schemas import (
    ApiCheckResponse,
    ConfigStatus,
    DiscoverEntityTypesRequest,
    DiscoverEntityTypesResponse,
    IndexRequest,
    IndexStatus,
)
from app.services import indexing_service

log = logging.getLogger("graphrag-api")
router = APIRouter()


# ── Indexing ─────────────────────────────────────────────────────────────


@router.post("/datasets/{dataset_id}/index", response_model=IndexStatus)
def start_indexing(dataset_id: str, body: IndexRequest):
    """Kick off GraphRAG indexing for a dataset.

    Returns the initial status immediately; poll /index/status for updates.
    """
    return indexing_service.start_indexing(
        dataset_id=dataset_id,
        entity_types=body.entity_types,
    )


@router.get("/datasets/{dataset_id}/index/status")
async def index_status_poll(dataset_id: str):
    """Simple polling endpoint that returns current indexing status.

    Client should poll this endpoint every 2-3 seconds to get updates.
    Much more reliable than SSE for this use case.
    """
    status = indexing_service.get_status(dataset_id)
    log.info("Status poll for dataset %s: status=%s, progress=%s, step=%s",
             dataset_id, status.status, status.progress, status.step)
    return status.model_dump()


# ── Entity-type discovery ────────────────────────────────────────────────


@router.post(
    "/datasets/{dataset_id}/discover-entity-types",
    response_model=DiscoverEntityTypesResponse,
)
def discover_entity_types(dataset_id: str, body: DiscoverEntityTypesRequest):
    """Use the LLM to discover entity types from sample text."""
    types = indexing_service.discover_entity_types(body.sample_text)
    return DiscoverEntityTypesResponse(entity_types=types)


# ── Config endpoints ─────────────────────────────────────────────────────


@router.get("/config/status", response_model=ConfigStatus)
def config_status():
    """Return whether LLM is configured and basic config details."""
    llm = get_llm_config()
    return ConfigStatus(
        configured=is_config_valid(),
        model=llm.get("model", ""),
        api_base=llm.get("api_base", ""),
        emb_model=llm.get("emb_model", ""),
    )


@router.post("/config/check-api", response_model=ApiCheckResponse)
def check_api():
    """Test connectivity to both Chat and Embedding API endpoints."""
    return indexing_service._check_api_connectivity()
