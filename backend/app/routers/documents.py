"""Document upload and management routes."""

from __future__ import annotations

from fastapi import APIRouter, File, UploadFile

from app.models.schemas import DocumentListResponse, UploadResponse
from app.services import document_service

router = APIRouter()


@router.post("/{dataset_id}/documents", response_model=UploadResponse)
async def upload_documents(
    dataset_id: str,
    files: list[UploadFile] = File(...),
):
    """Upload one or more documents to a dataset.

    Supported formats: .txt, .md, .csv, .pdf, .docx
    PDF/DOCX are automatically extracted to .txt.
    """
    docs = await document_service.upload_documents(dataset_id, files)
    return UploadResponse(uploaded=len(docs), documents=docs)


@router.get("/{dataset_id}/documents", response_model=DocumentListResponse)
def list_documents(dataset_id: str):
    """List all documents in a dataset's input/ directory."""
    docs = document_service.list_documents(dataset_id)
    return DocumentListResponse(dataset_id=dataset_id, documents=docs)


@router.delete("/{dataset_id}/documents/{filename}")
def delete_document(dataset_id: str, filename: str):
    """Delete a single document from a dataset."""
    document_service.delete_document(dataset_id, filename)
    return {"deleted": True}
