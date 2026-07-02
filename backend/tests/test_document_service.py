"""Tests for app.services.document_service."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException, UploadFile

from app.services import document_service


class TestAllowedExtensions:
    @pytest.mark.parametrize("ext", [".pdf", ".txt", ".md", ".csv", ".jpg", ".png",
                                      ".docx", ".pptx", ".xlsx", ".doc", ".tiff"])
    def test_allowed(self, ext):
        assert ext in document_service.ALLOWED_EXTENSIONS

    def test_rejects_unknown(self):
        assert ".exe" not in document_service.ALLOWED_EXTENSIONS
        assert ".zip" not in document_service.ALLOWED_EXTENSIONS


class TestUploadDocuments:
    @pytest.mark.asyncio
    async def test_upload_saves_file(self, dataset_dir):
        upload = UploadFile(filename="test.txt", file=__import__("io").BytesIO(b"hello"))
        docs = await document_service.upload_documents("test_ds", [upload])
        assert len(docs) == 1
        assert docs[0].name == "test.txt"
        assert docs[0].size == 5
        assert (dataset_dir / "input" / "test.txt").read_bytes() == b"hello"

    @pytest.mark.asyncio
    async def test_upload_rejects_bad_extension(self, dataset_dir):
        upload = UploadFile(filename="evil.exe", file=__import__("io").BytesIO(b""))
        with pytest.raises(HTTPException) as exc_info:
            await document_service.upload_documents("test_ds", [upload])
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_upload_missing_dataset_raises_404(self, tmp_data_root):
        upload = UploadFile(filename="f.txt", file=__import__("io").BytesIO(b""))
        with pytest.raises(HTTPException) as exc_info:
            await document_service.upload_documents("no_such_ds", [upload])
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_upload_multiple_files(self, dataset_dir):
        files = [
            UploadFile(filename="a.txt", file=__import__("io").BytesIO(b"aaa")),
            UploadFile(filename="b.pdf", file=__import__("io").BytesIO(b"bbb")),
        ]
        docs = await document_service.upload_documents("test_ds", files)
        assert len(docs) == 2


class TestListDocuments:
    def test_empty_input(self, dataset_dir):
        docs = document_service.list_documents("test_ds")
        assert docs == []

    def test_lists_files(self, dataset_dir):
        (dataset_dir / "input" / "a.txt").write_bytes(b"aaa")
        (dataset_dir / "input" / "b.pdf").write_bytes(b"bbb")
        docs = document_service.list_documents("test_ds")
        assert len(docs) == 2
        names = {d.name for d in docs}
        assert names == {"a.txt", "b.pdf"}

    def test_missing_dataset_raises_404(self, tmp_data_root):
        with pytest.raises(HTTPException) as exc_info:
            document_service.list_documents("no_such_ds")
        assert exc_info.value.status_code == 404


class TestDeleteDocument:
    def test_deletes_file(self, dataset_dir):
        f = dataset_dir / "input" / "del.txt"
        f.write_bytes(b"data")
        document_service.delete_document("test_ds", "del.txt")
        assert not f.exists()

    def test_missing_file_raises_404(self, dataset_dir):
        with pytest.raises(HTTPException) as exc_info:
            document_service.delete_document("test_ds", "nope.txt")
        assert exc_info.value.status_code == 404

    def test_missing_dataset_raises_404(self, tmp_data_root):
        with pytest.raises(HTTPException) as exc_info:
            document_service.delete_document("no_such_ds", "f.txt")
        assert exc_info.value.status_code == 404
