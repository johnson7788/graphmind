"""Dataset management routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.models.schemas import DatasetCreate, DatasetInfo, DatasetListResponse
from app.services import dataset_service

router = APIRouter()


@router.get("", response_model=DatasetListResponse)
def list_datasets():
    """List all datasets (newest first)."""
    datasets = dataset_service.list_datasets()
    return DatasetListResponse(datasets=datasets)


@router.post("", response_model=DatasetInfo, status_code=201)
def create_dataset(body: DatasetCreate):
    """Create a new dataset."""
    import re
    import uuid
    dataset_id = re.sub(r"[^a-zA-Z0-9_-]", "_", body.name)
    dataset_id = f"{dataset_id}_{uuid.uuid4().hex[:6]}"
    return dataset_service.create_dataset(dataset_id, body.name)


@router.get("/{dataset_id}", response_model=DatasetInfo)
def get_dataset(dataset_id: str):
    """Get info for a single dataset."""
    return dataset_service.get_dataset(dataset_id)


@router.delete("/{dataset_id}")
def delete_dataset(dataset_id: str):
    """Delete an entire dataset."""
    dataset_service.delete_dataset(dataset_id)
    return {"deleted": True}
