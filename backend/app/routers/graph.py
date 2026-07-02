"""Graph visualization and data-browsing routes."""

from __future__ import annotations

from fastapi import APIRouter, Query
from fastapi.responses import FileResponse

from app.models.schemas import GraphData, GraphStats, PaginatedResponse
from app.services import graph_service

router = APIRouter()


@router.get("/{dataset_id}/graph", response_model=GraphData)
async def get_graph(
    dataset_id: str,
    types: str = Query(default="", description="Comma-separated entity types to filter"),
    limit: int = Query(default=200, ge=1, le=2000),
):
    """Return graph data (nodes + edges) for frontend visualization."""
    type_list = [t.strip() for t in types.split(",") if t.strip()] or None
    return await graph_service.get_graph_data(dataset_id, types=type_list, limit=limit)


@router.get("/{dataset_id}/graph/stats", response_model=GraphStats)
async def get_graph_stats(dataset_id: str):
    """Return summary statistics for the knowledge graph."""
    return await graph_service.get_graph_stats(dataset_id)


@router.get("/{dataset_id}/graph/search-entities")
async def search_entities(
    dataset_id: str,
    q: str = Query(..., min_length=1, description="Fuzzy search query"),
    limit: int = Query(default=20, ge=1, le=100),
):
    """Fuzzy-search entity names for the entity explorer."""
    return await graph_service.search_entity_names(dataset_id, q, limit=limit)


@router.get("/{dataset_id}/graph/neighborhood", response_model=GraphData)
async def get_entity_neighborhood(
    dataset_id: str,
    entity: str = Query(..., description="Entity name to explore"),
    depth: int = Query(default=3, ge=1, le=5),
):
    """Return subgraph of an entity's N-level neighborhood."""
    return await graph_service.get_entity_neighborhood(dataset_id, entity, depth=depth)


@router.get("/{dataset_id}/graph/image")
def get_graph_image(
    dataset_id: str,
    path: str = Query(..., description="Dataset-relative image path"),
):
    """Serve a multimodal entity's image thumbnail (validated to the dataset)."""
    file_path = graph_service.resolve_image_file(dataset_id, path)
    return FileResponse(file_path)


@router.get("/{dataset_id}/entities", response_model=PaginatedResponse)
async def get_entities(
    dataset_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
):
    """Return paginated entities."""
    return await graph_service.get_entities(dataset_id, page=page, page_size=page_size)


@router.get("/{dataset_id}/relationships", response_model=PaginatedResponse)
async def get_relationships(
    dataset_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
):
    """Return paginated relationships."""
    return await graph_service.get_relationships(dataset_id, page=page, page_size=page_size)
