"""Tests for app.services.indexing_service (status management + progress callback)."""

from __future__ import annotations

from app.services.indexing_service import (
    _ProgressCallback,
    _FILES_BASE,
    _FILES_SPAN,
    _set_status,
    get_status,
    _index_status,
)
from app.models.schemas import IndexStatus


class TestStatusManagement:
    def setup_method(self):
        _index_status.clear()

    def test_get_status_default_idle(self):
        s = get_status("ds_new")
        assert s.status == "idle"
        assert s.dataset_id == "ds_new"

    def test_set_status_creates_entry(self):
        _set_status("ds1", status="running", step="building", progress=50)
        s = get_status("ds1")
        assert s.status == "running"
        assert s.step == "building"
        assert s.progress == 50

    def test_set_status_updates_existing(self):
        _set_status("ds1", status="running", progress=30)
        _set_status("ds1", status="completed", progress=100)
        s = get_status("ds1")
        assert s.status == "completed"
        assert s.progress == 100

    def test_set_status_with_error(self):
        _set_status("ds1", status="failed", error="API timeout")
        s = get_status("ds1")
        assert s.status == "failed"
        assert s.error == "API timeout"

    def test_start_indexing_returns_running(self):
        """start_indexing should immediately set status to running."""
        from app.services.indexing_service import start_indexing
        # Patch the thread to avoid actually running indexing
        import unittest.mock as mock
        with mock.patch("app.services.indexing_service.threading.Thread") as MockThread:
            MockThread.return_value.start = mock.MagicMock()
            result = start_indexing("ds_start")
            assert result.status == "running"
            assert result.step == "starting"

    def test_start_indexing_idempotent_when_running(self):
        _set_status("ds_run", status="running", step="building", progress=50)
        from app.services.indexing_service import start_indexing
        result = start_indexing("ds_run")
        # Should return current status without starting a new thread
        assert result.status == "running"
        assert result.progress == 50


class TestProgressCallback:
    def test_pct_calculation_single_file(self):
        cb = _ProgressCallback("ds", total=1)
        cb.begin_file(0, "file.pdf")
        # For 1 file: span = 60/1 = 60, base = 35 + 0*60 = 35
        assert cb._pct(0.0) == 35  # 35 + 0 * 60
        assert cb._pct(0.5) == 65  # 35 + 0.5 * 60 = 65
        assert cb._pct(1.0) == 94  # min(35 + 60, 94) = 94 (capped)

    def test_pct_calculation_multiple_files(self):
        cb = _ProgressCallback("ds", total=3)
        # File 0: span = 20, base = 35
        cb.begin_file(0, "a.pdf")
        assert cb._pct(0.0) == 35
        assert cb._pct(1.0) == 55  # 35 + 20

        # File 1: base = 35 + 20 = 55
        cb.begin_file(1, "b.pdf")
        assert cb._pct(0.0) == 55
        assert cb._pct(1.0) == 75  # 55 + 20

        # File 2: base = 35 + 40 = 75
        cb.begin_file(2, "c.pdf")
        assert cb._pct(0.0) == 75
        assert cb._pct(1.0) == 94  # min(95, 94) = 94

    def test_pct_never_exceeds_94(self):
        cb = _ProgressCallback("ds", total=1)
        cb.begin_file(0, "file.pdf")
        assert cb._pct(2.0) == 94

    def test_on_parse_start(self):
        _index_status.clear()
        cb = _ProgressCallback("ds_cb", total=1)
        cb.begin_file(0, "doc.pdf")
        cb.on_parse_start("/path/doc.pdf", parser="mineru")
        s = get_status("ds_cb")
        assert s.status == "running"
        assert "解析文档" in s.message

    def test_on_document_complete(self):
        _index_status.clear()
        cb = _ProgressCallback("ds_cb", total=1)
        cb.begin_file(0, "doc.pdf")
        cb.on_document_complete("/path/doc.pdf")
        s = get_status("ds_cb")
        assert s.status == "running"
        assert "完成" in s.message
