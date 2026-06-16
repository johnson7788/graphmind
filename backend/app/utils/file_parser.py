"""File text extraction utilities."""

from __future__ import annotations

import io
import logging
from pathlib import Path

log = logging.getLogger("graphrag-backend")


def extract_text(file_name: str, file_bytes: bytes) -> str:
    """Extract text content from PDF / DOCX / plain-text files.

    Supported formats:
    - .pdf  -> PyPDF2
    - .docx -> python-docx
    - .txt / .md / .csv -> UTF-8 decode

    Returns extracted plain text.
    """
    ext = Path(file_name).suffix.lower()
    if ext == ".pdf":
        from PyPDF2 import PdfReader

        reader = PdfReader(io.BytesIO(file_bytes))
        parts: list[str] = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                parts.append(text)
        return "\n\n".join(parts)
    elif ext == ".docx":
        from docx import Document

        doc = Document(io.BytesIO(file_bytes))
        parts = []
        for para in doc.paragraphs:
            if para.text.strip():
                parts.append(para.text)
        return "\n".join(parts)
    else:
        # .txt / .md / .csv — direct decode
        return file_bytes.decode("utf-8", errors="replace")
