"""Search (Q&A) routes."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.models.schemas import SearchRequest, SearchResponse
from app.services import search_service

router = APIRouter()


@router.post("/{dataset_id}/search", response_model=SearchResponse)
async def search(dataset_id: str, body: SearchRequest):
    """Run a knowledge-graph search query (non-streaming).

    Modes (LightRAG): naive | local | global | hybrid | mix.
    "basic" is accepted as an alias for "naive".
    """
    return await search_service.search(
        dataset_id=dataset_id,
        query=body.query,
        mode=body.mode,
        multimodal_content=body.multimodal_content,
    )


@router.post("/{dataset_id}/search/stream")
async def search_stream(dataset_id: str, body: SearchRequest):
    """Run a knowledge-graph search query with SSE streaming.

    Streams events:
    - status: {status, message} — progress updates
    - chunk:  {text}            — answer text
    - done:   {query, mode, answer} — final result
    - error:  {message}         — error occurred
    """
    return StreamingResponse(
        search_service.search_stream(
            dataset_id=dataset_id,
            query=body.query,
            mode=body.mode,
            multimodal_content=body.multimodal_content,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
