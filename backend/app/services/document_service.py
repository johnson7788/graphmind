"""Document upload, listing, and deletion service.

Original files are preserved as-is under ``data/<dataset_id>/input/`` so that
MinerU (via RAG-Anything) can parse the native format — PDF, images, Office
documents, and multimodal content — during indexing. No text extraction or
encoding conversion happens at upload time anymore.
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import HTTPException, UploadFile

from app.config import DATA_ROOT
from app.models.schemas import DocumentInfo

log = logging.getLogger("graphrag-backend")

# Formats MinerU / RAG-Anything can parse. Office formats require LibreOffice.
ALLOWED_EXTENSIONS = {
    ".pdf",
    ".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".gif", ".webp",
    ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx",
    ".txt", ".md", ".csv",
}


def _input_dir(dataset_id: str) -> Path:
    """Return the input/ directory for a dataset, creating it if needed."""
    d = DATA_ROOT / dataset_id / "input"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _ensure_dataset(dataset_id: str) -> None:
    """Raise 404 if the dataset directory does not exist."""
    if not (DATA_ROOT / dataset_id).is_dir():
        raise HTTPException(status_code=404, detail=f"Dataset '{dataset_id}' not found")


async def upload_documents(dataset_id: str, files: list[UploadFile]) -> list[DocumentInfo]:
    """Save uploaded files verbatim to data/<dataset_id>/input/.

    Files keep their original name and bytes; MinerU parses them at index time.
    """
    _ensure_dataset(dataset_id)
    input_dir = _input_dir(dataset_id)
    log.info("Uploading %d files to %s", len(files), input_dir)
    docs: list[DocumentInfo] = []

    for f in files:
        ext = Path(f.filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {ext}. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
            )

        file_bytes = await f.read()
        dest = input_dir / Path(f.filename).name
        dest.write_bytes(file_bytes)
        log.info("Saved: %s (%d bytes)", dest.name, len(file_bytes))
        docs.append(DocumentInfo(name=dest.name, size=len(file_bytes)))

    log.info("Upload complete: %d files saved to %s", len(docs), input_dir)
    return docs


def list_documents(dataset_id: str) -> list[DocumentInfo]:
    """List all documents in a dataset's input/ directory."""
    _ensure_dataset(dataset_id)
    input_dir = DATA_ROOT / dataset_id / "input"
    if not input_dir.exists():
        return []

    docs: list[DocumentInfo] = []
    for f in sorted(input_dir.iterdir()):
        if f.is_file():
            docs.append(DocumentInfo(name=f.name, size=f.stat().st_size))
    return docs


def delete_document(dataset_id: str, filename: str) -> None:
    """Delete a single document from a dataset's input/ directory."""
    _ensure_dataset(dataset_id)
    file_path = DATA_ROOT / dataset_id / "input" / filename
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail=f"File '{filename}' not found")
    file_path.unlink()
    log.info("Deleted document: %s/%s", dataset_id, filename)
