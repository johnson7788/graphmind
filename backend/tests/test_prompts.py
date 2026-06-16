"""Tests for the language-adaptive prompt templates (app.utils.prompts).

These tests verify that:
1. The extract_graph prompt explicitly instructs the LLM to preserve entity
   names in the original source language (e.g. "肺" stays "肺", not "lung").
2. Entity types may remain in English — this is acceptable and expected.
3. The prompt contains domain-specific examples (medical, historical) that
   demonstrate correct language-preservation behavior.
4. The old graphrag library instruction "Return output in English" is NOT
   present anywhere in our custom prompts.
5. write_prompts() correctly creates all required prompt files on disk.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from app.utils.prompts import get_extract_graph_prompt, write_prompts


# ── Helpers ──────────────────────────────────────────────────────────────


@pytest.fixture
def extract_prompt() -> str:
    """Return the extract_graph prompt template."""
    return get_extract_graph_prompt()


@pytest.fixture
def written_prompts_dir() -> Path:
    """Write prompts to a temporary directory and return the root path."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_prompts(root)
        yield root


# ── Language-preservation rules ──────────────────────────────────────────


class TestLanguagePreservationRules:
    """Verify the prompt enforces strict language-preservation for entity names."""

    def test_critical_language_rules_present(self, extract_prompt: str) -> None:
        """The prompt must contain an explicit 'CRITICAL LANGUAGE RULES' section."""
        assert "CRITICAL LANGUAGE RULES" in extract_prompt

    def test_no_translate_instruction(self, extract_prompt: str) -> None:
        """The prompt must explicitly forbid translating entity names."""
        assert "Do NOT translate entity names" in extract_prompt
        assert "NEVER translate" in extract_prompt

    def test_chinese_entity_name_example_lung(self, extract_prompt: str) -> None:
        """The prompt must explicitly use 肺 (not lung) as an example.

        This is the core requirement: a Chinese medical document mentioning
        '肺' must produce the entity name '肺', not its English translation.
        """
        # The prompt explicitly calls out this exact case
        assert '"肺"' in extract_prompt
        assert '"lung"' in extract_prompt
        # The instruction says "MUST be 肺, NOT lung"
        assert 'MUST be "肺", NOT "lung"' in extract_prompt

    def test_chinese_entity_name_example_drug(self, extract_prompt: str) -> None:
        """The prompt must explicitly use 阿莫西林 (not amoxicillin) as an example."""
        assert '"阿莫西林"' in extract_prompt
        assert '"amoxicillin"' in extract_prompt
        assert 'MUST be "阿莫西林", NOT "amoxicillin"' in extract_prompt

    def test_entity_type_english_ok(self, extract_prompt: str) -> None:
        """The prompt must clarify that entity types in English are acceptable."""
        assert "may be in English" in extract_prompt
        assert "this is acceptable" in extract_prompt

    def test_no_return_output_in_english(self, extract_prompt: str) -> None:
        """The old graphrag default instruction must NOT be present.

        The upstream graphrag library's default extract_graph prompt contains
        'Return output in English' which forces all entity names to English.
        Our custom prompt must NOT contain this instruction.
        """
        assert "Return output in English" not in extract_prompt

    def test_same_language_for_descriptions(self, extract_prompt: str) -> None:
        """Entity descriptions must be in the same language as source text."""
        assert "SAME LANGUAGE as the source text" in extract_prompt


# ── Medical domain example ────────────────────────────────────────────────


class TestMedicalDomainExample:
    """Verify the prompt includes a Chinese medical domain example."""

    def test_medical_example_label(self, extract_prompt: str) -> None:
        """The prompt must include a clearly-labeled medical document example."""
        assert "医学文档" in extract_prompt
        assert "Chinese input" in extract_prompt
        assert "Chinese output" in extract_prompt

    def test_medical_example_entity_types_in_english(self, extract_prompt: str) -> None:
        """Medical example entity types must be in English (organ, disease, etc.)."""
        assert "Entity_types: organ, disease, drug, symptom, medical_procedure" in extract_prompt

    def test_medical_example_entity_names_in_chinese(self, extract_prompt: str) -> None:
        """Medical example entity names must be in Chinese, matching source text."""
        # 肺 (lungs), 肺炎 (pneumonia), 阿莫西林 (amoxicillin),
        # 咳嗽 (cough), 发热 (fever), 呼吸困难 (dyspnea),
        # 支气管镜检查 (bronchoscopy)
        chinese_entity_names = [
            "肺",
            "肺炎",
            "咳嗽",
            "发热",
            "呼吸困难",
            "阿莫西林",
            "支气管镜检查",
        ]
        for name in chinese_entity_names:
            # Each name must appear inside an entity tuple in the example output
            assert f'("entity"<|>{name}<|>' in extract_prompt, (
                f"Chinese entity name '{name}' not found in entity output format"
            )

    def test_medical_example_relationships_in_chinese(
        self, extract_prompt: str
    ) -> None:
        """Relationship descriptions in the medical example must be in Chinese."""
        # At least one relationship with Chinese description must be present
        assert '("relationship"<|>肺<|>肺炎<|>' in extract_prompt
        assert '("relationship"<|>阿莫西林<|>肺炎<|>' in extract_prompt

    def test_medical_example_no_english_entity_names(
        self, extract_prompt: str
    ) -> None:
        """The Chinese medical example must NOT have English entity names."""
        # These English terms must NOT appear as entity names in the output
        english_terms_in_medical = [
            "lungs",
            "pneumonia",
            "cough",
            "fever",
            "dyspnea",
            "bronchoscopy",
        ]
        # Split prompt at the medical example section to isolate it
        medical_start = extract_prompt.find("Example 1")
        medical_end = extract_prompt.find("Example 2")
        assert medical_start != -1, "Example 1 (medical) not found"
        assert medical_end != -1, "Example 2 not found"
        medical_section = extract_prompt[medical_start:medical_end]

        for term in english_terms_in_medical:
            # English term must NOT appear as entity_name in ("entity"<|>NAME<|>
            pattern = f'("entity"<|>{term}<|>'
            assert pattern not in medical_section, (
                f"English entity name '{term}' found in Chinese medical example"
            )


# ── English example ───────────────────────────────────────────────────────


class TestEnglishExample:
    """Verify the prompt includes an English domain example."""

    def test_english_example_label(self, extract_prompt: str) -> None:
        assert "English input" in extract_prompt
        assert "English output" in extract_prompt

    def test_english_example_entity_names_in_english(
        self, extract_prompt: str
    ) -> None:
        """English example must have entity names in English."""
        english_names = ["lungs", "Pneumonia", "Amoxicillin", "cough", "fever"]
        for name in english_names:
            assert f'("entity"<|>{name}<|>' in extract_prompt


# ── Historical example ────────────────────────────────────────────────────


class TestHistoricalExample:
    """Verify the prompt includes a Chinese historical domain example."""

    def test_historical_example_label(self, extract_prompt: str) -> None:
        assert "历史文档" in extract_prompt

    def test_historical_example_entity_types_in_english(
        self, extract_prompt: str
    ) -> None:
        """Historical example entity types should be in English."""
        # Find the historical example section
        hist_start = extract_prompt.find("Example 2")
        hist_end = extract_prompt.find("Example 3")
        assert hist_start != -1
        assert hist_end != -1
        hist_section = extract_prompt[hist_start:hist_end]
        assert "Entity_types: person, location, event, organization, concept" in hist_section

    def test_historical_example_entity_names_in_chinese(
        self, extract_prompt: str
    ) -> None:
        """Historical example entity names must be in Chinese."""
        hist_start = extract_prompt.find("Example 2")
        hist_end = extract_prompt.find("Example 3")
        hist_section = extract_prompt[hist_start:hist_end]
        chinese_names = ["胤禛", "马武", "李卫", "八旗", "西藏"]
        for name in chinese_names:
            assert f'("entity"<|>{name}<|>' in hist_section, (
                f"Chinese entity name '{name}' not found in historical example"
            )


# ── Prompt file writing ──────────────────────────────────────────────────


class TestWritePrompts:
    """Verify write_prompts() creates all required files correctly."""

    def test_creates_prompts_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_prompts(root)
            assert (root / "prompts").is_dir()

    def test_creates_extract_graph_file(self, written_prompts_dir: Path) -> None:
        f = written_prompts_dir / "prompts" / "extract_graph.txt"
        assert f.exists()
        assert f.stat().st_size > 0

    def test_creates_summarize_descriptions_file(
        self, written_prompts_dir: Path
    ) -> None:
        f = written_prompts_dir / "prompts" / "summarize_descriptions.txt"
        assert f.exists()

    def test_creates_community_report_graph_file(
        self, written_prompts_dir: Path
    ) -> None:
        f = written_prompts_dir / "prompts" / "community_report_graph.txt"
        assert f.exists()

    def test_creates_community_report_text_file(
        self, written_prompts_dir: Path
    ) -> None:
        f = written_prompts_dir / "prompts" / "community_report_text.txt"
        assert f.exists()

    def test_extract_graph_file_matches_template(
        self, written_prompts_dir: Path
    ) -> None:
        """The written file must exactly match the in-memory template."""
        written = (written_prompts_dir / "prompts" / "extract_graph.txt").read_text()
        template = get_extract_graph_prompt()
        assert written == template

    def test_extract_graph_file_no_english_forcing(
        self, written_prompts_dir: Path
    ) -> None:
        """The written file must NOT contain the graphrag default English instruction."""
        written = (written_prompts_dir / "prompts" / "extract_graph.txt").read_text()
        assert "Return output in English" not in written

    def test_summarize_descriptions_same_language(
        self, written_prompts_dir: Path
    ) -> None:
        """summarize_descriptions.txt must instruct to write in the same language."""
        written = (
            written_prompts_dir / "prompts" / "summarize_descriptions.txt"
        ).read_text()
        assert "SAME LANGUAGE" in written
        assert "Do not translate" in written

    def test_community_reports_same_language(
        self, written_prompts_dir: Path
    ) -> None:
        """Community report prompts must instruct to write in the same language."""
        for name in ("community_report_graph.txt", "community_report_text.txt"):
            written = (written_prompts_dir / "prompts" / name).read_text()
            assert "SAME LANGUAGE" in written
            assert "Do not translate" in written


# ── Prompt template variable placeholders ─────────────────────────────────


class TestPromptPlaceholders:
    """Verify the template contains required {placeholder} variables."""

    def test_entity_types_placeholder(self, extract_prompt: str) -> None:
        assert "{entity_types}" in extract_prompt

    def test_input_text_placeholder(self, extract_prompt: str) -> None:
        assert "{input_text}" in extract_prompt
