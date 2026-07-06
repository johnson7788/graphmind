"""Central RAG engine: builds model functions and manages per-dataset
RAGAnything (LightRAG + MinerU multimodal) instances.

Replaces the previous Microsoft GraphRAG CLI orchestration. Each dataset gets
an isolated RAGAnything instance whose LightRAG storage lives under
``data/<dataset>/rag_storage`` and whose MinerU parse output lives under
``data/<dataset>/output``.
"""

from __future__ import annotations

import asyncio
import logging
from functools import partial
from pathlib import Path
from typing import Any, Callable, Optional

from lightrag import LightRAG
from lightrag.llm.openai import openai_complete_if_cache, openai_embed
from lightrag.utils import EmbeddingFunc

from raganything import RAGAnything, RAGAnythingConfig

from app.config import DATA_ROOT, get_llm_config

log = logging.getLogger("graphmind.rag_engine")


# ── Storage layout helpers ────────────────────────────────────────────────
def dataset_root(dataset_id: str) -> Path:
    return DATA_ROOT / dataset_id


def rag_storage_dir(dataset_id: str) -> Path:
    return dataset_root(dataset_id) / "rag_storage"


def parse_output_dir(dataset_id: str) -> Path:
    return dataset_root(dataset_id) / "output"


# ── Model function factories ──────────────────────────────────────────────
def build_llm_model_func(llm: dict) -> Callable:
    """Async text-completion function bound to the configured OpenAI-compatible API."""

    async def llm_model_func(
        prompt: str,
        system_prompt: Optional[str] = None,
        history_messages: Optional[list] = None,
        **kwargs: Any,
    ) -> str:
        return await openai_complete_if_cache(
            llm["model"],
            prompt,
            system_prompt=system_prompt,
            history_messages=history_messages or [],
            api_key=llm["api_key"],
            base_url=llm["api_base"],
            **kwargs,
        )

    return llm_model_func


def build_vision_model_func(llm: dict, llm_model_func: Callable) -> Callable:
    """Async vision function handling both RAG-Anything call patterns:

    1. ``vision_model_func(prompt, system_prompt=..., image_data=<base64>)``
       from the multimodal processors (image captioning during indexing).
    2. ``vision_model_func("", messages=[...])`` from VLM-enhanced query,
       where ``messages`` already contains interleaved text + image_url parts.

    Falls back to the plain text LLM when no image is present.
    """

    async def vision_model_func(
        prompt: str,
        system_prompt: Optional[str] = None,
        history_messages: Optional[list] = None,
        image_data: Optional[str] = None,
        messages: Optional[list] = None,
        **kwargs: Any,
    ) -> str:
        if messages:
            return await openai_complete_if_cache(
                llm["vision_model"],
                "",
                api_key=llm["api_key"],
                base_url=llm["vision_base"],
                messages=messages,
                **kwargs,
            )
        if image_data:
            vlm_messages: list[dict] = []
            if system_prompt:
                vlm_messages.append({"role": "system", "content": system_prompt})
            vlm_messages.append(
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_data}"
                            },
                        },
                    ],
                }
            )
            return await openai_complete_if_cache(
                llm["vision_model"],
                "",
                api_key=llm["api_key"],
                base_url=llm["vision_base"],
                messages=vlm_messages,
                **kwargs,
            )
        return await llm_model_func(
            prompt,
            system_prompt=system_prompt,
            history_messages=history_messages or [],
            **kwargs,
        )

    return vision_model_func


def build_embedding_func(llm: dict) -> EmbeddingFunc:
    # ``openai_embed`` is itself an EmbeddingFunc pre-wrapped with a hardcoded
    # embedding_dim of 1536. Wrapping it again in a partial hides that inner
    # wrapper from EmbeddingFunc's auto-unwrap, so the inner 1536 dimension check
    # would clash with our real dim (e.g. 1024 for text-embedding-v3). Bind the
    # raw underlying coroutine (``openai_embed.func``) instead, and inject the
    # configured dimension via send_dimensions so it is requested from the API.
    return EmbeddingFunc(
        embedding_dim=llm["emb_dim"],
        send_dimensions=True,
        func=partial(
            openai_embed.func,
            model=llm["emb_model"],
            api_key=llm["api_key"],
            base_url=llm["emb_base"],
        ),
    )


# ── Per-dataset RAGAnything instance manager ──────────────────────────────
_instances: dict[str, RAGAnything] = {}
_locks: dict[str, asyncio.Lock] = {}
_global_lock = asyncio.Lock()


def _make_config(dataset_id: str) -> RAGAnythingConfig:
    return RAGAnythingConfig(
        working_dir=str(rag_storage_dir(dataset_id)),
        parser="mineru",
        # 'auto' 会触发 mineru 的 pdf_classify，其内部调用 PdfImage.get_pos，
        # 该方法在 pypdfium2 5.9.0（被 pdftext 硬钉）中已移除 → mineru 内部虽能
        # 捕获并回退，但会在 stderr 打出 ERROR 行，raganything 的
        # _run_mineru_command 见到任何含 "error" 的行即判定解析失败。
        # 'ocr' 直接跳过 classify，多模态输出（图片/表格/公式）不受影响。
        parse_method="ocr",
        parser_output_dir=str(parse_output_dir(dataset_id)),
        enable_image_processing=True,
        enable_table_processing=True,
        enable_equation_processing=True,
    )


def _create_instance(
    dataset_id: str, entity_types: Optional[list[str]] = None
) -> RAGAnything:
    llm = get_llm_config()
    llm_model_func = build_llm_model_func(llm)
    vision_model_func = build_vision_model_func(llm, llm_model_func)
    embedding_func = build_embedding_func(llm)

    rag_storage_dir(dataset_id).mkdir(parents=True, exist_ok=True)
    parse_output_dir(dataset_id).mkdir(parents=True, exist_ok=True)

    addon_params: dict[str, Any] = {}
    language = llm_config_language()
    if language:
        addon_params["language"] = language
    if entity_types:
        addon_params["entity_types"] = entity_types

    lightrag_kwargs: dict[str, Any] = {}
    if addon_params:
        lightrag_kwargs["addon_params"] = addon_params

    return RAGAnything(
        llm_model_func=llm_model_func,
        vision_model_func=vision_model_func,
        embedding_func=embedding_func,
        config=_make_config(dataset_id),
        lightrag_kwargs=lightrag_kwargs,
    )


def llm_config_language() -> Optional[str]:
    """Optional summary/extraction language from config (e.g. 'Simplified Chinese')."""
    from app.config import APP_CONFIG

    rag_cfg = APP_CONFIG.get("rag", {}) or {}
    return rag_cfg.get("language") or None


async def _dataset_lock(dataset_id: str) -> asyncio.Lock:
    async with _global_lock:
        lock = _locks.get(dataset_id)
        if lock is None:
            lock = asyncio.Lock()
            _locks[dataset_id] = lock
        return lock


async def get_rag(dataset_id: str) -> RAGAnything:
    """Return an initialized RAGAnything instance for the dataset (cached)."""
    inst = _instances.get(dataset_id)
    if inst is not None:
        return inst

    lock = await _dataset_lock(dataset_id)
    async with lock:
        inst = _instances.get(dataset_id)
        if inst is not None:
            return inst
        inst = _create_instance(dataset_id)
        init = await inst._ensure_lightrag_initialized()
        if not init or not init.get("success"):
            raise RuntimeError(
                f"RAGAnything 初始化失败: {(init or {}).get('error', 'unknown error')}"
            )
        _patch_modal_processor_config(inst)
        _instances[dataset_id] = inst
        log.info("Initialized RAGAnything for dataset %s", dataset_id)
        return inst


def _patch_modal_processor_config(inst: RAGAnything) -> None:
    """Make RAG-Anything 1.3.1's multimodal path work against LightRAG 1.5+.

    LightRAG 1.5 introduced runtime-only config keys — ``role_llm_funcs`` (the
    per-role wrapped LLM callables) and ``llm_cache_identities`` — that it
    injects via ``_build_global_config()`` rather than storing as dataclass
    fields. RAG-Anything 1.3.1 predates this and builds its config two ways,
    both of which drop those keys:

    * multimodal *extraction* uses ``asdict(lightrag)`` (per processor) →
      ``KeyError: 'role_llm_funcs'`` in ``extract_entities``;
    * the cross-item *merge* passes ``lightrag.__dict__`` directly →
      ``KeyError: 'role_llm_funcs'`` in ``merge_nodes_and_edges`` (summarize).

    Without both, every image/table/equation item is dropped and
    ``process_document_complete`` aborts. Fix by (1) handing each processor the
    correctly-built config and (2) injecting the runtime keys into
    ``lightrag.__dict__`` so the raw-dict merge path finds them too. (These are
    properties on the class, so the dict entries coexist with normal attribute
    access rather than shadowing it.)
    """
    lightrag = inst.lightrag
    if not hasattr(lightrag, "_build_global_config"):
        return
    global_config = lightrag._build_global_config()
    for proc in (inst.modal_processors or {}).values():
        proc.global_config = global_config
    for key in ("role_llm_funcs", "llm_cache_identities"):
        if key in global_config:
            lightrag.__dict__[key] = global_config[key]


async def get_lightrag(dataset_id: str) -> LightRAG:
    """Return the underlying initialized LightRAG instance (for graph reads)."""
    return (await get_rag(dataset_id)).lightrag


async def evict(dataset_id: str) -> None:
    """Finalize and drop a dataset's cached instance (e.g. after deletion)."""
    lock = await _dataset_lock(dataset_id)
    async with lock:
        inst = _instances.pop(dataset_id, None)
        if inst is not None:
            try:
                await inst.finalize_storages()
            except Exception as e:  # noqa: BLE001
                log.warning("Error finalizing RAG for %s: %s", dataset_id, e)
