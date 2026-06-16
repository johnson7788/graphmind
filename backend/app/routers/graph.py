"""Graph visualization and data-browsing routes."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.models.schemas import GraphData, GraphStats, PaginatedResponse
from app.services import graph_service

router = APIRouter()


@router.get("/{dataset_id}/graph", response_model=GraphData)
def get_graph(
    dataset_id: str,
    types: str = Query(default="", description="Comma-separated entity types to filter"),
    limit: int = Query(default=200, ge=1, le=2000),
):
    """Return graph data (nodes + edges) for frontend visualization."""
    type_list = [t.strip() for t in types.split(",") if t.strip()] or None
    return graph_service.get_graph_data(dataset_id, types=type_list, limit=limit)


@router.get("/{dataset_id}/graph/stats", response_model=GraphStats)
def get_graph_stats(dataset_id: str):
    """Return summary statistics for the knowledge graph."""
    return graph_service.get_graph_stats(dataset_id)


@router.get("/{dataset_id}/graph/search-entities")
def search_entities(
    dataset_id: str,
    q: str = Query(..., min_length=1, description="Fuzzy search query"),
    limit: int = Query(default=20, ge=1, le=100),
):
    """Fuzzy-search entity names for the entity explorer."""
    return graph_service.search_entity_names(dataset_id, q, limit=limit)


@router.get("/{dataset_id}/graph/neighborhood", response_model=GraphData)
def get_entity_neighborhood(
    dataset_id: str,
    entity: str = Query(..., description="Entity name to explore"),
    depth: int = Query(default=3, ge=1, le=5),
):
    """Return subgraph of an entity's N-level neighborhood."""
    return graph_service.get_entity_neighborhood(dataset_id, entity, depth=depth)


@router.get("/{dataset_id}/entities", response_model=PaginatedResponse)
def get_entities(
    dataset_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
):
    """Return paginated entities."""
    return graph_service.get_entities(dataset_id, page=page, page_size=page_size)


@router.get("/{dataset_id}/relationships", response_model=PaginatedResponse)
def get_relationships(
    dataset_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
):
    """Return paginated relationships."""
    return graph_service.get_relationships(dataset_id, page=page, page_size=page_size)


@router.get("/{dataset_id}/communities")
def get_communities(dataset_id: str):
    """Return all community reports (summary view)."""
    return graph_service.get_communities(dataset_id)


@router.get("/{dataset_id}/communities/{community_id}")
def get_community_detail(dataset_id: str, community_id: str):
    """Return full detail for a single community report."""
    result = graph_service.get_community_detail(dataset_id, community_id)
    if result is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Community '{community_id}' not found")
    return result
