"""Tests for discover_entity_types (app.services.indexing_service).

These tests verify that:
1. The LLM prompt requests entity types in ENGLISH (not source language).
2. Comma-separated types are parsed correctly from the LLM response.
3. Formatting artifacts (quotes, brackets) are stripped.
4. Fallback to DEFAULT_ENTITY_TYPES when the LLM returns nothing useful.
5. The prompt used for discovery mentions English explicitly.
"""

from __future__ import annotations

import io
import json
from unittest.mock import MagicMock, patch

import pytest

from app.config import DEFAULT_ENTITY_TYPES
from app.services.indexing_service import discover_entity_types


# ── Helpers ──────────────────────────────────────────────────────────────


def _mock_llm_config() -> dict:
    return {
        "api_key": "test-key-abc",
        "model": "gpt-4o-test",
        "api_base": "https://api.test.example.com/v1",
        "emb_model": "text-embedding-test",
        "emb_base": "https://api.test.example.com/v1",
    }


def _make_mock_response(content: str) -> MagicMock:
    """Create a mock urllib response object that returns a chat completion."""
    body = json.dumps({
        "choices": [{"message": {"content": content}}],
    }).encode("utf-8")
    mock_resp = MagicMock()
    mock_resp.read.return_value = body
    mock_resp.__enter__ = lambda self: self
    mock_resp.__exit__ = lambda self, *args: None
    return mock_resp


# ── Prompt content tests ─────────────────────────────────────────────────


class TestDiscoverPromptContent:
    """Verify the prompt sent to the LLM requests English entity types."""

    @patch("app.services.indexing_service.urllib.request.urlopen")
    @patch("app.services.indexing_service.get_llm_config", return_value=_mock_llm_config())
    def test_prompt_requests_english_types(
        self, _mock_config: MagicMock, mock_urlopen: MagicMock
    ) -> None:
        """The prompt must ask for entity types in English regardless of input."""
        mock_urlopen.return_value = _make_mock_response("person, organization, location")

        # Capture the request sent to the API
        captured_requests = []

        def capture_request(req, **kwargs):
            captured_requests.append(req)
            return _make_mock_response("person, organization, location")

        mock_urlopen.side_effect = capture_request

        discover_entity_types("这是一段中文测试文本，包含各种实体。")

        assert len(captured_requests) == 1
        req = captured_requests[0]
        payload = json.loads(req.data.decode("utf-8"))
        prompt_text = payload["messages"][0]["content"]

        # The prompt must explicitly request English entity types
        assert "in ENGLISH" in prompt_text or "in English" in prompt_text
        assert "MUST be in English" in prompt_text
        # Must NOT say "use same language as input text"
        assert "SAME LANGUAGE as the input text" not in prompt_text


# ── Response parsing tests ────────────────────────────────────────────────


class TestDiscoverResponseParsing:
    """Verify entity types are correctly parsed from LLM responses."""

    @patch("app.services.indexing_service.urllib.request.urlopen")
    @patch("app.services.indexing_service.get_llm_config", return_value=_mock_llm_config())
    def test_parse_comma_separated_types(
        self, _mock_config: MagicMock, mock_urlopen: MagicMock
    ) -> None:
        """Standard comma-separated types should be parsed correctly."""
        mock_urlopen.return_value = _make_mock_response(
            "person, organization, location, event, technology"
        )
        result = discover_entity_types("Some sample text.")
        assert result == ["person", "organization", "location", "event", "technology"]

    @patch("app.services.indexing_service.urllib.request.urlopen")
    @patch("app.services.indexing_service.get_llm_config", return_value=_mock_llm_config())
    def test_parse_types_with_extra_whitespace(
        self, _mock_config: MagicMock, mock_urlopen: MagicMock
    ) -> None:
        """Extra whitespace around types should be stripped."""
        mock_urlopen.return_value = _make_mock_response(
            "  person  ,  disease  ,  drug  ,  symptom  "
        )
        result = discover_entity_types("Medical document text.")
        assert result == ["person", "disease", "drug", "symptom"]

    @patch("app.services.indexing_service.urllib.request.urlopen")
    @patch("app.services.indexing_service.get_llm_config", return_value=_mock_llm_config())
    def test_strip_formatting_artifacts(
        self, _mock_config: MagicMock, mock_urlopen: MagicMock
    ) -> None:
        """Quotes, brackets, and parentheses should be stripped from types."""
        mock_urlopen.return_value = _make_mock_response(
            '["person", "organization", "location"]'
        )
        result = discover_entity_types("Text with entities.")
        assert result == ["person", "organization", "location"]

    @patch("app.services.indexing_service.urllib.request.urlopen")
    @patch("app.services.indexing_service.get_llm_config", return_value=_mock_llm_config())
    def test_parse_medical_domain_types(
        self, _mock_config: MagicMock, mock_urlopen: MagicMock
    ) -> None:
        """Medical domain entity types should be parsed correctly."""
        mock_urlopen.return_value = _make_mock_response(
            "organ, disease, drug, symptom, medical_procedure, body_part"
        )
        result = discover_entity_types("肺是人体重要的呼吸器官。肺炎是肺部感染性疾病。")
        assert "organ" in result
        assert "disease" in result
        assert "drug" in result
        assert "symptom" in result


# ── Fallback behavior ─────────────────────────────────────────────────────


class TestDiscoverFallback:
    """Verify fallback to DEFAULT_ENTITY_TYPES when LLM returns empty."""

    @patch("app.services.indexing_service.urllib.request.urlopen")
    @patch("app.services.indexing_service.get_llm_config", return_value=_mock_llm_config())
    def test_fallback_on_empty_response(
        self, _mock_config: MagicMock, mock_urlopen: MagicMock
    ) -> None:
        """If LLM returns empty string, should fall back to DEFAULT_ENTITY_TYPES."""
        mock_urlopen.return_value = _make_mock_response("")
        result = discover_entity_types("Some text.")
        assert result == list(DEFAULT_ENTITY_TYPES)

    @patch("app.services.indexing_service.urllib.request.urlopen")
    @patch("app.services.indexing_service.get_llm_config", return_value=_mock_llm_config())
    def test_fallback_on_only_whitespace(
        self, _mock_config: MagicMock, mock_urlopen: MagicMock
    ) -> None:
        """If LLM returns only whitespace, should fall back to DEFAULT_ENTITY_TYPES."""
        mock_urlopen.return_value = _make_mock_response("   \n  ")
        result = discover_entity_types("Some text.")
        assert result == list(DEFAULT_ENTITY_TYPES)

    @patch("app.services.indexing_service.urllib.request.urlopen")
    @patch("app.services.indexing_service.get_llm_config", return_value=_mock_llm_config())
    def test_fallback_on_only_punctuation(
        self, _mock_config: MagicMock, mock_urlopen: MagicMock
    ) -> None:
        """If LLM returns only punctuation artifacts, should fall back."""
        mock_urlopen.return_value = _make_mock_response('[]""()')
        result = discover_entity_types("Some text.")
        assert result == list(DEFAULT_ENTITY_TYPES)


# ── Default entity types are in English ───────────────────────────────────


class TestDefaultEntityTypes:
    """Verify DEFAULT_ENTITY_TYPES are in English (as required)."""

    def test_defaults_are_english(self) -> None:
        """DEFAULT_ENTITY_TYPES must all be in English."""
        english_types = {
            "organization", "person", "location", "event", "concept", "technology",
        }
        assert set(DEFAULT_ENTITY_TYPES) == english_types

    def test_defaults_not_empty(self) -> None:
        assert len(DEFAULT_ENTITY_TYPES) > 0
