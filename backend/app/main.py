"""FastAPI application entry point."""

from __future__ import annotations

import logging
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.routers import datasets, documents, indexing, graph, search

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

log = logging.getLogger("graphrag-api")

app = FastAPI(
    title="GraphRAG Demo API",
    description="Knowledge graph construction, visualization and Q&A",
    version="1.0.0",
)

# CORS — allow Vite dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request logging middleware ────────────────────────────────────────────


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log every /api/ request with method, path, status, and duration."""
    path = request.url.path

    # Only log /api/ routes (skip static files, docs, etc.)
    if not path.startswith("/api/"):
        return await call_next(request)

    # SSE endpoints are long-lived — log start only
    is_sse = "index/status" in path or "search/stream" in path

    start = time.time()
    log.info(
        "→ %s %s%s",
        request.method,
        path,
        f"?{request.url.query}" if request.url.query else "",
    )

    response = await call_next(request)
    duration = time.time() - start

    if is_sse:
        log.info(
            "← %s %s %d (%.1fs, SSE stream)",
            request.method, path, response.status_code, duration,
        )
    else:
        log.info(
            "← %s %s %d (%.1fs)",
            request.method, path, response.status_code, duration,
        )

    return response


# ── Routers ───────────────────────────────────────────────────────────────

app.include_router(datasets.router, prefix="/api/datasets", tags=["datasets"])
app.include_router(documents.router, prefix="/api/datasets", tags=["documents"])
app.include_router(indexing.router, prefix="/api", tags=["indexing"])
app.include_router(graph.router, prefix="/api/datasets", tags=["graph"])
app.include_router(search.router, prefix="/api/datasets", tags=["search"])


@app.get("/api/health")
def health():
    return {"status": "ok"}
