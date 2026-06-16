"""Knowledge graph search service — wraps graphrag.api search functions."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import AsyncGenerator

import pandas as pd

from app.config import DATA_ROOT
from app.models.schemas import SearchResponse
from app.services.graph_service import load_parquet

log = logging.getLogger("graphrag-backend")

# Tables required by each search mode
_REQUIRED_TABLES = {
    "local": ["entities", "relationships", "communities", "community_reports", "text_units"],
    "global": ["entities", "communities", "community_reports"],
    "basic": ["text_units"],
}

_MODE_LABELS = {
    "local": "本地搜索",
    "global": "全局搜索",
    "basic": "基础 RAG",
}


def _check_index_complete(dataset_path: str, mode: str) -> list[str]:
    """Return list of missing required tables for the given search mode."""
    output_dir = Path(dataset_path) / "output"
    missing = []
    for table in _REQUIRED_TABLES.get(mode, []):
        if not (output_dir / f"{table}.parquet").exists():
            missing.append(table)
    return missing


def _load_table(dataset_path: str, table: str) -> pd.DataFrame:
    """Load a parquet table, raising ValueError if not found."""
    df = load_parquet(dataset_path, table)
    if df is None:
        raise ValueError(f"Required table '{table}' not found")
    return df


def _sse_event(event: str, data: dict) -> str:
    """Format an SSE event string."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _load_graphrag_data(
    query: str, mode: str, dataset_path: str
) -> tuple[object, dict[str, pd.DataFrame]]:
    """Load config and parquet tables for streaming search (synchronous).

    Returns (config, tables_dict).  Called from a worker thread so it doesn't
    block the event loop.
    """
    from graphrag.config.load_config import load_config

    config = load_config(Path(dataset_path))
    required = set(_REQUIRED_TABLES[mode])
    tables: dict[str, pd.DataFrame] = {}
    for t in required:
        tables[t] = _load_table(dataset_path, t)

    log.info(
        "Search data loaded (mode=%s): %s",
        mode,
        ", ".join(f"{k}={len(v)}" for k, v in tables.items()),
    )
    return config, tables


def _build_search_stream(
    query: str,
    mode: str,
    config: object,
    tables: dict[str, pd.DataFrame],
):
    """Build and return a graphrag streaming async generator.

    Must be called from the FastAPI event loop because the returned
    ``AsyncGenerator`` contains coroutines bound to the running loop.
    The graphrag ``*_streaming`` helpers are *regular* (non-async) factory
    functions that synchronously build the search engine and then return
    ``search_engine.stream_search(query)``, an ``AsyncGenerator[str, None]``
    that yields one LLM delta-token per iteration.
    """
    import graphrag.api as graphrag_api

    if mode == "local":
        return graphrag_api.local_search_streaming(
            config=config,
            entities=tables["entities"],
            communities=tables["communities"],
            community_reports=tables["community_reports"],
            text_units=tables["text_units"],
            relationships=tables["relationships"],
            covariates=None,
            community_level=0,
            response_type="Multiple Paragraphs",
            query=query,
        )
    elif mode == "global":
        return graphrag_api.global_search_streaming(
            config=config,
            entities=tables["entities"],
            communities=tables["communities"],
            community_reports=tables["community_reports"],
            community_level=0,
            dynamic_community_selection=True,
            response_type="Multiple Paragraphs",
            query=query,
        )
    else:  # basic
        return graphrag_api.basic_search_streaming(
            config=config,
            text_units=tables["text_units"],
            response_type="Multiple Paragraphs",
            query=query,
        )


def _run_graphrag_search(query: str, mode: str, dataset_path: str) -> str:
    """Run graphrag search synchronously (called from a worker thread).

    Returns the answer string. Raises on error.
    """
    from graphrag.config.load_config import load_config
    from graphrag.config.models.graph_rag_config import GraphRagConfig
    import graphrag.api as graphrag_api

    config: GraphRagConfig = load_config(Path(dataset_path))

    required = set(_REQUIRED_TABLES[mode])
    tables: dict[str, pd.DataFrame] = {}
    for t in required:
        tables[t] = _load_table(dataset_path, t)

    log.info(
        "Search data loaded (mode=%s): %s",
        mode,
        ", ".join(f"{k}={len(v)}" for k, v in tables.items()),
    )

    async def _search() -> str:
        if mode == "local":
            result, _ = await graphrag_api.local_search(
                config=config,
                entities=tables["entities"],
                communities=tables["communities"],
                community_reports=tables["community_reports"],
                text_units=tables["text_units"],
                relationships=tables["relationships"],
                covariates=None,
                community_level=0,
                response_type="Multiple Paragraphs",
                query=query,
            )
        elif mode == "global":
            result, _ = await graphrag_api.global_search(
                config=config,
                entities=tables["entities"],
                communities=tables["communities"],
                community_reports=tables["community_reports"],
                community_level=0,
                dynamic_community_selection=True,
                response_type="Multiple Paragraphs",
                query=query,
            )
        else:  # basic
            result, _ = await graphrag_api.basic_search(
                config=config,
                text_units=tables["text_units"],
                response_type="Multiple Paragraphs",
                query=query,
            )
        return str(result)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_search())
    finally:
        loop.close()


# ── Streaming search (SSE) ──────────────────────────────────────────────


async def search_stream(
    dataset_id: str, query: str, mode: str
) -> AsyncGenerator[str, None]:
    """Async generator yielding SSE events for streaming search.

    Event types:
    - status:  {status, message}  — progress updates
    - chunk:   {text}             — incremental answer text (one LLM token per event)
    - done:    {query, mode, answer, time} — final result
    - error:   {message}          — error occurred
    """
    dataset_path = str(DATA_ROOT / dataset_id)

    # Validate index completeness
    missing = _check_index_complete(dataset_path, mode)
    if missing:
        mode_label = _MODE_LABELS.get(mode, mode)
        answer = (
            f"**{mode_label}不可用** — 索引数据不完整。\n\n"
            f"缺少以下数据表: {', '.join(missing)}\n\n"
            f"可能原因:\n"
            f"- 索引仍在进行中，请等待完成\n"
            f"- 索引过程中出错，请查看日志或重新构建\n\n"
            f"💡 如果只需要基础 RAG，可以尝试「基础 RAG」模式（仅需 text_units 表）。"
        )
        yield _sse_event("error", {"message": answer})
        return

    # Phase 1: Loading data (synchronous I/O — offloaded to a worker thread)
    yield _sse_event("status", {"status": "preparing", "message": "正在加载索引数据..."})

    try:
        config, tables = await asyncio.to_thread(
            _load_graphrag_data, query, mode, dataset_path
        )
    except Exception as e:
        log.exception("Failed to load data for dataset %s", dataset_id)
        yield _sse_event("error", {"message": f"**加载数据出错:** {e}"})
        return

    # Phase 2: Searching — build the streaming generator in the FastAPI event
    # loop so its internal coroutines are bound to the running loop.
    yield _sse_event("status", {"status": "searching", "message": "正在搜索中，可能需要 10-30 秒..."})

    try:
        stream = _build_search_stream(query, mode, config, tables)

        # Phase 3: Stream tokens one by one
        full_answer = ""
        async for chunk in stream:
            full_answer += chunk
            yield _sse_event("chunk", {"text": chunk})

        # Phase 4: Done
        yield _sse_event("done", {
            "query": query,
            "mode": mode,
            "answer": full_answer,
            "time": "",
        })
    except Exception as e:
        log.exception("Streaming search error for dataset %s", dataset_id)
        yield _sse_event("error", {"message": f"**搜索出错:** {e}"})


# ── Non-streaming search (legacy) ───────────────────────────────────────


def _run_search(dataset_id: str, query: str, mode: str) -> SearchResponse:
    """Execute a graphrag search and return the answer (non-streaming)."""
    dataset_path = str(DATA_ROOT / dataset_id)

    missing = _check_index_complete(dataset_path, mode)
    if missing:
        mode_label = _MODE_LABELS.get(mode, mode)
        return SearchResponse(
            query=query,
            mode=mode,
            answer=(
                f"**{mode_label}不可用** — 索引数据不完整。\n\n"
                f"缺少以下数据表: {', '.join(missing)}\n\n"
                f"可能原因:\n"
                f"- 索引仍在进行中，请等待完成\n"
                f"- 索引过程中出错，请查看日志或重新构建\n\n"
                f"💡 如果只需要基础 RAG，可以尝试「基础 RAG」模式（仅需 text_units 表）。"
            ),
        )

    try:
        answer = _run_graphrag_search(query, mode, dataset_path)
        return SearchResponse(query=query, mode=mode, answer=answer)
    except Exception as e:
        log.exception("Search error for dataset %s", dataset_id)
        return SearchResponse(
            query=query,
            mode=mode,
            answer=f"**搜索出错:** {e}",
        )


def search(dataset_id: str, query: str, mode: str = "local") -> SearchResponse:
    """Public entry point for non-streaming search."""
    if not (DATA_ROOT / dataset_id).is_dir():
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Dataset '{dataset_id}' not found")

    if mode not in ("local", "global", "basic"):
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=f"Invalid search mode: {mode}")

    return _run_search(dataset_id, query, mode)
