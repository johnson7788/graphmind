"""Document upload, listing, and deletion service."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import HTTPException, UploadFile

from app.config import DATA_ROOT
from app.models.schemas import DocumentInfo
from app.utils.file_parser import extract_text

log = logging.getLogger("graphrag-backend")

ALLOWED_EXTENSIONS = {".txt", ".md", ".csv", ".pdf", ".docx"}


def _decode_to_utf8(raw: bytes, filename: str) -> str:
    """Detect encoding and decode to str, trying common encodings.

    Handles UTF-8 (with/without BOM), UTF-16, GBK/GB2312, and Latin-1 fallback.
    """
    # Try UTF-8 first (most common)
    try:
        return raw.decode("utf-8-sig")  # handles UTF-8 BOM
    except UnicodeDecodeError:
        pass

    # Try UTF-16 only if BOM is present (0xff 0xfe or 0xfe 0xff)
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        try:
            text = raw.decode("utf-16")
            log.info("Decoded %s with encoding: utf-16 (BOM detected)", filename)
            return text
        except (UnicodeDecodeError, ValueError):
            pass

    # Try GBK/GB2312 (common for Chinese text files)
    for enc in ("gbk", "gb2312", "gb18030"):
        try:
            text = raw.decode(enc)
            log.info("Decoded %s with encoding: %s", filename, enc)
            return text
        except UnicodeDecodeError:
            continue

    # Try Latin-1 as last resort (never fails, but may produce garbage)
    log.warning("Could not detect encoding for %s, falling back to latin-1", filename)
    return raw.decode("latin-1")


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
    """Parse uploaded files and save them to data/<dataset_id>/input/.

    All files (PDF, DOCX, TXT, MD, CSV) are extracted/converted to .txt
    since GraphRAG requires UTF-8 encoded .txt files in the input/ directory.
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
                detail=f"Unsupported file type: {ext}. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
            )

        file_bytes = await f.read()

        if ext in (".pdf", ".docx"):
            # Extract text and save as .txt
            text = extract_text(f.filename, file_bytes)
            txt_name = Path(f.filename).stem + ".txt"
            dest = input_dir / txt_name
            dest.write_text(text, encoding="utf-8")
            log.info("Extracted text: %s -> %s (%d chars)", f.filename, txt_name, len(text))
            docs.append(DocumentInfo(
                name=txt_name,
                size=len(text.encode("utf-8")),
                extracted_chars=len(text),
            ))
        else:
            # Decode to UTF-8 (handle various encodings: GBK, UTF-16, etc.)
            # GraphRAG requires UTF-8 encoded .txt files, so normalize all
            # plain-text extensions (.md, .csv, .txt) to .txt
            stem = Path(f.filename).stem
            txt_name = stem + ".txt"
            dest = input_dir / txt_name

            text = _decode_to_utf8(file_bytes, f.filename)
            dest.write_text(text, encoding="utf-8")
            char_count = len(text)
            log.info("Saved: %s -> %s (%d chars, UTF-8)", f.filename, txt_name, char_count)
            docs.append(DocumentInfo(
                name=txt_name,
                size=len(text.encode("utf-8")),
                extracted_chars=char_count,
            ))

    log.info("Upload complete: %d files saved to %s", len(docs), input_dir)
    for f in sorted(input_dir.iterdir()):
        if f.is_file():
            log.info("  - %s (%d bytes)", f.name, f.stat().st_size)
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
            docs.append(DocumentInfo(
                name=f.name,
                size=f.stat().st_size,
            ))
    return docs


def delete_document(dataset_id: str, filename: str) -> None:
    """Delete a single document from a dataset's input/ directory."""
    _ensure_dataset(dataset_id)
    file_path = DATA_ROOT / dataset_id / "input" / filename
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail=f"File '{filename}' not found")
    file_path.unlink()
    log.info("Deleted document: %s/%s", dataset_id, filename)
