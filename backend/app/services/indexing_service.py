"""Indexing service — parses & indexes documents with RAG-Anything (MinerU).

Each dataset's input files are processed through RAGAnything's
``process_document_complete`` pipeline: MinerU parses the native file
(PDF/image/Office/text) into text + multimodal blocks, which are then inserted
into the dataset's LightRAG storage. Progress is reported to the frontend via
the same ``IndexStatus`` polling contract used by the old GraphRAG flow.
"""

from __future__ import annotations

import asyncio
import json as _json
import logging
import threading
import urllib.error
import urllib.request
from pathlib import Path

from raganything.callbacks import ProcessingCallback

from app.config import DATA_ROOT, DEFAULT_ENTITY_TYPES, get_llm_config
from app.models.schemas import ApiCheckResponse, IndexStatus
from app.services import rag_engine

log = logging.getLogger("graphrag-backend")

# Global status tracker: dataset_id -> IndexStatus
_index_status: dict[str, IndexStatus] = {}
_status_lock = threading.Lock()


def _set_status(dataset_id: str, **kwargs) -> None:
    """Update the indexing status for a dataset (thread-safe)."""
    with _status_lock:
        if dataset_id not in _index_status:
            _index_status[dataset_id] = IndexStatus(dataset_id=dataset_id, status="idle")
        current = _index_status[dataset_id]
        updated = current.model_dump()
        updated.update(kwargs)
        _index_status[dataset_id] = IndexStatus(**updated)
        if kwargs.get("status") in ("completed", "failed"):
            log.info("Status update for %s: %s", dataset_id, kwargs.get("status"))
        elif kwargs.get("progress"):
            log.debug("Progress update for %s: %s%%", dataset_id, kwargs.get("progress"))


def get_status(dataset_id: str) -> IndexStatus:
    """Return the current indexing status for a dataset."""
    with _status_lock:
        return _index_status.get(
            dataset_id,
            IndexStatus(dataset_id=dataset_id, status="idle"),
        )


def _check_api_connectivity() -> ApiCheckResponse:
    """Test both chat and embedding API endpoints for connectivity."""
    llm = get_llm_config()

    def _test_endpoint(api_base: str, api_key: str, model: str, path: str, label: str) -> str | None:
        url = api_base.rstrip("/") + path
        if path == "/chat/completions":
            body_dict = {"model": model, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 5}
        else:
            body_dict = {"model": model, "input": "test"}
        body = _json.dumps(body_dict).encode("utf-8")
        try:
            req = urllib.request.Request(url, data=body, method="POST")
            req.add_header("Content-Type", "application/json")
            req.add_header("Authorization", f"Bearer {api_key}")
            resp = urllib.request.urlopen(req, timeout=30)
            data = _json.loads(resp.read())
            if "choices" in data or "data" in data:
                log.info("%s connectivity check passed", label)
                return None
            return f"{label} unexpected response: {str(data)[:300]}"
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")[:500]
            return f"{label} failed (HTTP {e.code}): {body}"
        except Exception as e:
            return f"{label} connection failed: {e}"

    chat_err = _test_endpoint(
        llm["api_base"], llm["api_key"], llm["model"],
        "/chat/completions", "Chat model",
    )
    emb_base = llm.get("emb_base") or llm["api_base"]
    emb_err = _test_endpoint(
        emb_base, llm["api_key"], llm["emb_model"],
        "/embeddings", "Embedding model",
    )

    return ApiCheckResponse(
        chat_ok=chat_err is None,
        embedding_ok=emb_err is None,
        chat_error=chat_err,
        embedding_error=emb_err,
    )


def discover_entity_types(sample_text: str) -> list[str]:
    """Call the LLM to automatically discover entity types from sample text."""
    llm = get_llm_config()
    sample = sample_text[:4000]

    prompt = """You are an expert at identifying entity types in text.
Given the following text, identify the most relevant entity types (categories) that would be useful for knowledge graph extraction.

Rules:
- Return ONLY a comma-separated list of entity type names in ENGLISH (e.g., person, organization, location, disease, drug, organ, symptom)
- Entity types should be general categories, not specific instances
- Avoid overly generic types like "other" or "thing"
- Aim for 5-12 types that best fit the content
- Entity type names MUST be in English regardless of the input text language

Text:
{sample}

Entity types (comma-separated, in English):""".format(sample=sample)

    api_key = llm["api_key"]
    base = llm["api_base"].rstrip("/")
    model = llm["model"]

    payload = _json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens": 256,
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{base}/chat/completions",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = _json.loads(resp.read().decode("utf-8"))

    content = data["choices"][0]["message"]["content"].strip()
    types = [t.strip() for t in content.split(",") if t.strip()]
    types = [t.strip('"\'[]()') for t in types]
    types = [t for t in types if t and len(t) < 30]
    return types if types else list(DEFAULT_ENTITY_TYPES)


# ── Progress callback ─────────────────────────────────────────────────────
# Overall progress uses 35→95 for document processing; 25→35 is reserved for
# preflight/API-check and 95→100 for finalization.
_FILES_BASE = 35
_FILES_SPAN = 60


class _ProgressCallback(ProcessingCallback):
    """Maps RAG-Anything processing events onto the IndexStatus progress bar."""

    def __init__(self, dataset_id: str, total: int) -> None:
        self.dataset_id = dataset_id
        self.total = max(total, 1)
        self.index = 0
        self.name = ""

    def begin_file(self, index: int, name: str) -> None:
        self.index = index
        self.name = name

    def _pct(self, fraction: float) -> int:
        slice_span = _FILES_SPAN / self.total
        base = _FILES_BASE + self.index * slice_span
        return min(int(base + fraction * slice_span), 94)

    def _update(self, fraction: float, message: str) -> None:
        _set_status(
            self.dataset_id,
            status="running",
            step="building",
            progress=self._pct(fraction),
            message=f"[{self.index + 1}/{self.total}] {message}",
        )

    def on_parse_start(self, file_path: str, parser: str = "", **kw) -> None:
        self._update(0.05, f"解析文档：{self.name}")

    def on_parse_complete(self, file_path: str, content_blocks: int = 0, **kw) -> None:
        self._update(0.40, f"解析完成（{content_blocks} 块）：{self.name}")

    def on_text_insert_start(self, file_path: str, text_length: int = 0, **kw) -> None:
        self._update(0.45, f"抽取实体与关系：{self.name}")

    def on_text_insert_complete(self, file_path: str, **kw) -> None:
        self._update(0.60, f"文本索引完成：{self.name}")

    def on_multimodal_start(self, file_path: str, item_count: int = 0, **kw) -> None:
        self._update(0.62, f"处理多模态内容（{item_count} 项）：{self.name}")

    def on_multimodal_item_complete(
        self, file_path: str, item_index: int = 0, item_type: str = "", total_items: int = 0, **kw
    ) -> None:
        frac = 0.62 + 0.36 * (item_index / max(total_items, 1))
        self._update(frac, f"多模态 {item_index}/{total_items}（{item_type}）：{self.name}")

    def on_document_complete(self, file_path: str, **kw) -> None:
        self._update(1.0, f"完成：{self.name}")


# ── Async indexing worker ─────────────────────────────────────────────────
async def _run_index_async(dataset_id: str, entity_types: list[str]) -> None:
    root = DATA_ROOT / dataset_id
    input_dir = root / "input"
    files = [f for f in sorted(input_dir.iterdir()) if f.is_file()] if input_dir.exists() else []

    log.info("=" * 60)
    log.info("INDEXING START: dataset=%s files=%d entity_types=%s",
             dataset_id, len(files), entity_types)

    if not files:
        _set_status(
            dataset_id, status="failed", step="preflight", progress=0,
            message="没有可索引的文档",
            error=f"未在 {input_dir} 中找到任何文档，请先上传文件。",
        )
        return

    _set_status(dataset_id, status="running", step="validating", progress=30,
                message="检查 API 连通性...")
    api_check = _check_api_connectivity()
    if not api_check.chat_ok:
        _set_status(dataset_id, status="failed", step="check api", progress=0,
                    message="API 连通性检查失败",
                    error=f"Chat API 检查失败:\n{api_check.chat_error}")
        return
    if not api_check.embedding_ok:
        _set_status(dataset_id, status="failed", step="check api", progress=0,
                    message="API 连通性检查失败",
                    error=f"Embedding API 检查失败:\n{api_check.embedding_error}")
        return

    _set_status(dataset_id, status="running", step="building", progress=_FILES_BASE,
                message="初始化知识图谱引擎...")

    inst = rag_engine._create_instance(dataset_id, entity_types=entity_types or None)
    init = await inst._ensure_lightrag_initialized()
    if not init or not init.get("success"):
        _set_status(dataset_id, status="failed", step="building", progress=0,
                    message="RAG 引擎初始化失败",
                    error=(init or {}).get("error", "unknown error"))
        return

    callback = _ProgressCallback(dataset_id, total=len(files))
    inst.callback_manager.register(callback)
    try:
        for i, fp in enumerate(files):
            callback.begin_file(i, fp.name)
            log.info("Processing document %d/%d: %s", i + 1, len(files), fp.name)
            await inst.process_document_complete(file_path=str(fp))
    finally:
        try:
            await inst.finalize_storages()
        except Exception as e:  # noqa: BLE001
            log.warning("finalize_storages error for %s: %s", dataset_id, e)
        # Drop any cached (query-loop) instance so reads reload fresh storage.
        rag_engine._instances.pop(dataset_id, None)

    _set_status(dataset_id, status="completed", step="done", progress=100,
                message="索引完成！", error=None)
    log.info("Indexing completed for dataset: %s", dataset_id)


def _run_index_thread(dataset_id: str, entity_types: list[str]) -> None:
    """Run the async indexing worker in a dedicated event loop."""
    try:
        asyncio.run(_run_index_async(dataset_id, entity_types))
    except Exception as e:
        log.exception("_run_index_thread exception")
        _set_status(dataset_id, status="failed", step="unknown", progress=0,
                    message="索引过程中出现错误", error=str(e))


def start_indexing(dataset_id: str, entity_types: list[str] | None = None) -> IndexStatus:
    """Start the indexing process in a background thread.

    Returns immediately with the initial status.
    """
    current = get_status(dataset_id)
    if current.status == "running":
        return current

    _set_status(dataset_id, status="running", step="starting", progress=25,
                message="开始索引...", error=None)

    et = entity_types or list(DEFAULT_ENTITY_TYPES)
    thread = threading.Thread(
        target=_run_index_thread,
        args=(dataset_id, et),
        daemon=True,
    )
    thread.start()

    return get_status(dataset_id)
