"""
Unit tests for core functions.

Run: uv run pytest tests/test_unit.py -v
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


# ── detect_pdf_type ──────────────────────────────────────────────────────────

class TestDetectPdfType:
    def _make_page(self, text: str) -> MagicMock:
        page = MagicMock()
        page.get_text.return_value = text
        return page

    @patch("src.pdf_parser.fitz.open")
    def test_scanned_pdf(self, mock_open):
        doc = MagicMock()
        doc.__iter__ = lambda self: iter([self._make_page("ab") for _ in range(3)])
        doc.__len__ = lambda self: 3
        mock_open.return_value = doc

        from src.pdf_parser import detect_pdf_type

        result = detect_pdf_type("dummy.pdf")
        assert result == "scanned"

    @patch("src.pdf_parser.fitz.open")
    def test_text_pdf(self, mock_open, tmp_path):
        doc = MagicMock()
        long_text = "这是一段很长的文本内容，用于测试 PDF 类型检测。" * 10
        doc.__iter__ = lambda self: iter([self._make_page(long_text) for _ in range(3)])
        doc.__len__ = lambda self: 3
        mock_open.return_value = doc

        from src.pdf_parser import detect_pdf_type

        result = detect_pdf_type("dummy.pdf")
        assert result == "text"


# ── split_chunks ─────────────────────────────────────────────────────────────

class TestSplitChunks:
    def test_table_block_not_split(self):
        from src.knowledge_base import split_chunks

        blocks = [{"page": 1, "type": "table", "source": "test.pdf", "clause_id": "", "content": "| A | B |\n|---|---|\n| 1 | 2 |"}]
        docs = split_chunks(blocks)
        assert len(docs) == 1
        assert docs[0].metadata["type"] == "table"

    def test_text_block_splits_on_size(self):
        from src.knowledge_base import split_chunks

        long_text = "这是一段很长的测试文本。" * 100
        blocks = [{"page": 2, "type": "text", "source": "test.pdf", "clause_id": "4.1", "content": long_text}]
        docs = split_chunks(blocks)
        assert len(docs) > 1
        for doc in docs:
            assert doc.metadata["page"] == 2
            assert doc.metadata["type"] == "text"

    def test_metadata_preserved(self):
        from src.knowledge_base import split_chunks

        blocks = [{"page": 5, "type": "text", "source": "doc.pdf", "clause_id": "3.2", "content": "短文本"}]
        docs = split_chunks(blocks)
        assert docs[0].metadata["clause_id"] == "3.2"
        assert docs[0].metadata["source"] == "doc.pdf"


# ── self_check fallback ───────────────────────────────────────────────────────

class TestSelfCheckFallback:
    def test_timeout_returns_fallback(self, monkeypatch):
        import signal as _signal
        from src import self_check as sc_module

        # Simulate timeout by making _call_llm raise _TimeoutError
        def fake_call_llm(prompt):
            raise sc_module._TimeoutError()

        monkeypatch.setattr(sc_module, "_call_llm", fake_call_llm)
        # Disable SIGALRM to avoid interference in test runner
        monkeypatch.setattr(_signal, "SIGALRM", None, raising=False)

        result = sc_module.self_check("q", "a", [])
        assert result["verdict"] == "uncertain"
        assert result["action"] == "warn"

    def test_invalid_json_returns_fallback(self):
        from src.self_check import _parse_json

        result = _parse_json("not valid json at all")
        assert result["verdict"] == "uncertain"
        assert result["action"] == "warn"

    def test_valid_supported_json(self):
        from src.self_check import _parse_json

        raw = '{"verdict": "supported", "reason": "直接支持", "action": "answer"}'
        result = _parse_json(raw)
        assert result["verdict"] == "supported"
        assert result["action"] == "answer"

    def test_valid_json_with_code_fence(self):
        from src.self_check import _parse_json

        raw = '```json\n{"verdict": "unsupported", "reason": "无依据", "action": "reject"}\n```'
        result = _parse_json(raw)
        assert result["verdict"] == "unsupported"
        assert result["action"] == "reject"

    def test_invalid_enum_values_normalized(self):
        from src.self_check import _parse_json

        raw = '{"verdict": "maybe", "reason": "x", "action": "unknown"}'
        result = _parse_json(raw)
        assert result["verdict"] == "uncertain"
        assert result["action"] == "warn"


# ── clause_id extraction ─────────────────────────────────────────────────────

class TestClauseIdExtraction:
    def test_extracts_clause(self):
        from src.pdf_parser import _extract_clause_id

        assert _extract_clause_id("4.1 技术要求") == "4.1"
        assert _extract_clause_id("5.2.3 检验方法") == "5.2.3"

    def test_no_clause(self):
        from src.pdf_parser import _extract_clause_id

        assert _extract_clause_id("普通段落没有编号") == ""
        assert _extract_clause_id("") == ""
