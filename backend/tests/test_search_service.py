"""Tests for app.services.search_service."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.search_service import _norm_mode, _sse_event, _VALID_MODES


class TestNormMode:
    def test_basic_maps_to_naive(self):
        assert _norm_mode("basic") == "naive"

    def test_other_modes_passthrough(self):
        for m in _VALID_MODES:
            assert _norm_mode(m) == m

    def test_unknown_passthrough(self):
        assert _norm_mode("unknown") == "unknown"


class TestSseEvent:
    def test_format(self):
        event = _sse_event("chunk", {"text": "hello"})
        assert event.startswith("event: chunk\n")
        assert '"text": "hello"' in event
        assert event.endswith("\n\n")

    def test_unicode(self):
        event = _sse_event("done", {"answer": "你好"})
        assert "你好" in event


class TestSearchStreamErrors:
    @pytest.mark.asyncio
    async def test_invalid_mode_yields_error(self):
        from app.services.search_service import search_stream
        events = []
        async for e in search_stream("ds", "query", "badmode"):
            events.append(e)
        assert len(events) == 1
        assert "error" in events[0]
        assert "无效的搜索模式" in events[0]

    @pytest.mark.asyncio
    async def test_missing_dataset_yields_error(self, tmp_data_root):
        from app.services.search_service import search_stream
        events = []
        async for e in search_stream("no_such_ds", "query", "mix"):
            events.append(e)
        assert len(events) == 1
        assert "不存在" in events[0]


class TestSearchNonStreaming:
    @pytest.mark.asyncio
    async def test_invalid_mode_raises_400(self, dataset_dir):
        from app.services.search_service import search
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await search("test_ds", "q", mode="badmode")
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_missing_dataset_raises_404(self, tmp_data_root):
        from app.services.search_service import search
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await search("no_ds", "q")
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_returns_answer_on_success(self, dataset_dir):
        from app.services.search_service import search
        mock_rag = AsyncMock()
        mock_rag.aquery = AsyncMock(return_value="The answer is 42.")
        with patch("app.services.search_service.get_rag", return_value=mock_rag):
            resp = await search("test_ds", "what?", mode="mix")
            assert resp.answer == "The answer is 42."
            assert resp.mode == "mix"
            assert resp.query == "what?"

    @pytest.mark.asyncio
    async def test_multimodal_uses_aquery_with_multimodal(self, dataset_dir):
        from app.services.search_service import search
        mock_rag = AsyncMock()
        mock_rag.aquery_with_multimodal = AsyncMock(return_value="VLM answer")
        with patch("app.services.search_service.get_rag", return_value=mock_rag):
            resp = await search(
                "test_ds", "describe", mode="mix",
                multimodal_content=[{"type": "image", "img_path": "img.png"}],
            )
            assert resp.answer == "VLM answer"
            mock_rag.aquery_with_multimodal.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_error_returns_error_message(self, dataset_dir):
        from app.services.search_service import search
        mock_rag = AsyncMock()
        mock_rag.aquery = AsyncMock(side_effect=RuntimeError("boom"))
        with patch("app.services.search_service.get_rag", return_value=mock_rag):
            resp = await search("test_ds", "q")
            assert "搜索出错" in resp.answer
            assert "boom" in resp.answer
