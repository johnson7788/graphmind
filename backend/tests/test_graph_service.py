"""Tests for app.services.graph_service (pure utilities + mocked graph)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.services.graph_service import (
    TYPE_COLORS,
    _color_for_type,
    _node_type,
    resolve_image_file,
)


class TestColorForType:
    def test_known_types(self):
        assert _color_for_type("person") == "#FF6B6B"
        assert _color_for_type("organization") == "#4ECDC4"
        assert _color_for_type("image") == "#E056A0"

    def test_case_insensitive(self):
        assert _color_for_type("Person") == "#FF6B6B"
        assert _color_for_type("ORGANIZATION") == "#4ECDC4"

    def test_unknown_falls_back(self):
        assert _color_for_type("unknown_type") == TYPE_COLORS["OTHER"]

    def test_whitespace_stripped(self):
        assert _color_for_type("  person  ") == "#FF6B6B"


class TestNodeType:
    def test_from_labels(self):
        node = MagicMock()
        node.labels = ["person"]
        node.properties = {"entity_type": "organization"}
        assert _node_type(node) == "person"

    def test_from_properties_when_no_labels(self):
        node = MagicMock()
        node.labels = []
        node.properties = {"entity_type": "location"}
        assert _node_type(node) == "location"

    def test_default_other(self):
        node = MagicMock()
        node.labels = []
        node.properties = {}
        assert _node_type(node) == "OTHER"


class TestResolveImageFile:
    def test_valid_image(self, dataset_dir):
        # Create an image file inside the dataset
        img_dir = dataset_dir / "output"
        img_dir.mkdir()
        img = img_dir / "fig1.png"
        img.write_bytes(b"\x89PNG")

        # patch dataset_root to return dataset_dir
        with patch("app.services.graph_service.dataset_root", return_value=dataset_dir):
            result = resolve_image_file("test_ds", "output/fig1.png")
            assert result == img.resolve()

    def test_path_escape_rejected(self, dataset_dir):
        with patch("app.services.graph_service.dataset_root", return_value=dataset_dir):
            with pytest.raises(HTTPException) as exc_info:
                resolve_image_file("test_ds", "../../etc/passwd")
            assert exc_info.value.status_code == 404

    def test_nonexistent_file_rejected(self, dataset_dir):
        with patch("app.services.graph_service.dataset_root", return_value=dataset_dir):
            with pytest.raises(HTTPException) as exc_info:
                resolve_image_file("test_ds", "no_such_file.png")
            assert exc_info.value.status_code == 404

    def test_missing_dataset_raises_404(self, tmp_data_root):
        with pytest.raises(HTTPException) as exc_info:
            resolve_image_file("nonexistent", "img.png")
        assert exc_info.value.status_code == 404


class TestNormalizeImage:
    """Test the _normalize_image helper."""

    def test_returns_none_for_nonexistent(self):
        from app.services.graph_service import _normalize_image
        with patch("app.services.graph_service.dataset_root", return_value=Path("/tmp/fake")):
            assert _normalize_image("ds", "nonexistent.png") is None

    def test_resolves_existing_file(self, dataset_dir):
        from app.services.graph_service import _normalize_image
        img = dataset_dir / "output" / "img.png"
        img.parent.mkdir(exist_ok=True)
        img.write_bytes(b"png")
        with patch("app.services.graph_service.dataset_root", return_value=dataset_dir):
            result = _normalize_image("test_ds", "output/img.png")
            assert result == "output/img.png"
