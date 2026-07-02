"""Pydantic request/response schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


# ── Dataset ──────────────────────────────────────────────────────────────

class DatasetCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Display name")


class DatasetInfo(BaseModel):
    id: str
    name: str
    created: str
    has_index: bool
    index_complete: bool = False
    entity_count: int = 0
    relationship_count: int = 0


class DatasetListResponse(BaseModel):
    datasets: list[DatasetInfo]


# ── Documents ────────────────────────────────────────────────────────────

class DocumentInfo(BaseModel):
    name: str
    size: int  # bytes
    extracted_chars: int = 0


class DocumentListResponse(BaseModel):
    dataset_id: str
    documents: list[DocumentInfo]


class UploadResponse(BaseModel):
    uploaded: int
    documents: list[DocumentInfo]


# ── Indexing ─────────────────────────────────────────────────────────────

class IndexRequest(BaseModel):
    entity_types: list[str] | None = None  # None = use defaults
    entity_type_mode: str = "default"      # "default" | "manual" | "auto"


class IndexStatus(BaseModel):
    dataset_id: str
    status: str          # "idle" | "running" | "completed" | "failed"
    step: str = ""
    progress: int = 0    # 0-100
    message: str = ""
    error: str | None = None


class DiscoverEntityTypesRequest(BaseModel):
    sample_text: str = Field(..., min_length=10)


class DiscoverEntityTypesResponse(BaseModel):
    entity_types: list[str]


# ── Config ───────────────────────────────────────────────────────────────

class ConfigStatus(BaseModel):
    configured: bool
    model: str = ""
    api_base: str = ""
    emb_model: str = ""


class ApiCheckResponse(BaseModel):
    chat_ok: bool
    embedding_ok: bool
    chat_error: str | None = None
    embedding_error: str | None = None


# ── Graph ────────────────────────────────────────────────────────────────

class GraphNode(BaseModel):
    id: str
    label: str
    type: str
    description: str
    color: str
    size: float
    image: str | None = None  # dataset-relative path to a thumbnail (image nodes)


class GraphEdge(BaseModel):
    from_: str = Field(alias="from")
    to: str
    label: str
    weight: float

    model_config = {"populate_by_name": True}


class GraphData(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class GraphStats(BaseModel):
    entity_count: int
    relationship_count: int
    entity_types: dict[str, int]


# ── Data Browser (paginated) ─────────────────────────────────────────────

class PaginatedResponse(BaseModel):
    items: list[dict]
    total: int
    page: int
    page_size: int


# ── Search ───────────────────────────────────────────────────────────────

class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    # LightRAG query modes; "basic" is accepted as an alias for "naive".
    mode: str = Field(default="mix", pattern="^(naive|local|global|hybrid|mix|basic)$")
    # Optional multimodal content (images/tables/equations) for VLM-enhanced Q&A.
    multimodal_content: list[dict] | None = None


class SearchResponse(BaseModel):
    query: str
    mode: str
    answer: str
    context: str | None = None
