"""Knowledge-graph search service — wraps RAG-Anything / LightRAG querying.

Text queries stream token-by-token via LightRAG's ``aquery(stream=True)``.
Multimodal queries (an image/table/equation attached to the question) use
RAG-Anything's ``aquery_with_multimodal`` for VLM-enhanced answering; these
return a single answer (streaming is not supported for the VLM path).
"""

from __future__ import annotations

import json
import logging
from typing import AsyncGenerator

from fastapi import HTTPException
from lightrag import QueryParam

from app.config import DATA_ROOT
from app.models.schemas import SearchResponse
from app.services.rag_engine import get_rag

log = logging.getLogger("graphrag-backend")

# LightRAG query modes; "basic" (old GraphRAG name) maps to LightRAG "naive".
_VALID_MODES = {"naive", "local", "global", "hybrid", "mix"}
_MODE_ALIASES = {"basic": "naive"}


def _norm_mode(mode: str) -> str:
    return _MODE_ALIASES.get(mode, mode)


def _sse_event(event: str, data: dict) -> str:
    """Format an SSE event string."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _ensure_dataset(dataset_id: str) -> None:
    if not (DATA_ROOT / dataset_id).is_dir():
        raise HTTPException(status_code=404, detail=f"Dataset '{dataset_id}' not found")


# ── Streaming search (SSE) ──────────────────────────────────────────────
async def search_stream(
    dataset_id: str,
    query: str,
    mode: str,
    multimodal_content: list[dict] | None = None,
) -> AsyncGenerator[str, None]:
    """Async generator yielding SSE events for streaming search.

    Event types:
    - status: {status, message}          — progress updates
    - chunk:  {text}                      — incremental answer text
    - done:   {query, mode, answer, time} — final result
    - error:  {message}                   — error occurred
    """
    mode = _norm_mode(mode)
    if mode not in _VALID_MODES:
        yield _sse_event("error", {"message": f"无效的搜索模式: {mode}"})
        return
    if not (DATA_ROOT / dataset_id).is_dir():
        yield _sse_event("error", {"message": f"数据集 '{dataset_id}' 不存在"})
        return

    yield _sse_event("status", {"status": "preparing", "message": "正在加载知识图谱..."})
    try:
        rag = await get_rag(dataset_id)
    except Exception as e:
        log.exception("Failed to load RAG for dataset %s", dataset_id)
        yield _sse_event("error", {"message": f"**加载知识图谱出错:** {e}"})
        return

    yield _sse_event("status", {"status": "searching", "message": "正在检索并生成回答..."})

    # Multimodal path: VLM-enhanced, non-streaming.
    if multimodal_content:
        try:
            answer = await rag.aquery_with_multimodal(
                query, multimodal_content=multimodal_content, mode=mode
            )
        except Exception as e:
            log.exception("Multimodal query error for dataset %s", dataset_id)
            yield _sse_event("error", {"message": f"**搜索出错:** {e}"})
            return
        yield _sse_event("chunk", {"text": answer})
        yield _sse_event("done", {"query": query, "mode": mode, "answer": answer, "time": ""})
        return

    # Text path: stream tokens from LightRAG.
    try:
        resp = await rag.lightrag.aquery(
            query, param=QueryParam(mode=mode, stream=True)
        )
        full_answer = ""
        if isinstance(resp, str):
            full_answer = resp
            yield _sse_event("chunk", {"text": resp})
        else:
            async for chunk in resp:
                if not chunk:
                    continue
                full_answer += chunk
                yield _sse_event("chunk", {"text": chunk})
        yield _sse_event("done", {"query": query, "mode": mode, "answer": full_answer, "time": ""})
    except Exception as e:
        log.exception("Streaming search error for dataset %s", dataset_id)
        yield _sse_event("error", {"message": f"**搜索出错:** {e}"})


# ── Retrieval only (no answer generation) ────────────────────────────────
async def retrieve_context(dataset_id: str, query: str, mode: str = "mix") -> dict:
    """Return the retrieved context (entities/relations/chunks) without LLM answer."""
    _ensure_dataset(dataset_id)
    mode = _norm_mode(mode)
    if mode not in _VALID_MODES:
        raise HTTPException(status_code=400, detail=f"Invalid search mode: {mode}")
    rag = await get_rag(dataset_id)
    context = await rag.lightrag.aquery(
        query, param=QueryParam(mode=mode, only_need_context=True)
    )
    return {"query": query, "mode": mode, "context": str(context)}


# ── Non-streaming search ─────────────────────────────────────────────────
async def search(
    dataset_id: str,
    query: str,
    mode: str = "mix",
    multimodal_content: list[dict] | None = None,
) -> SearchResponse:
    """Public entry point for non-streaming search (VLM-enhanced when possible)."""
    _ensure_dataset(dataset_id)
    mode = _norm_mode(mode)
    if mode not in _VALID_MODES:
        raise HTTPException(status_code=400, detail=f"Invalid search mode: {mode}")

    try:
        rag = await get_rag(dataset_id)
        if multimodal_content:
            answer = await rag.aquery_with_multimodal(
                query, multimodal_content=multimodal_content, mode=mode
            )
        else:
            answer = await rag.aquery(query, mode=mode)
        return SearchResponse(query=query, mode=mode, answer=str(answer))
    except Exception as e:
        log.exception("Search error for dataset %s", dataset_id)
        return SearchResponse(query=query, mode=mode, answer=f"**搜索出错:** {e}")
