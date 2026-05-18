"""
Public ask() interface: retrieval → generation → self-check → format.
"""
from __future__ import annotations

import logging
from pathlib import Path

from src.config import cfg
from src.knowledge_base import load_knowledge_base
from src.rag import build_prompt, format_sources, generate_answer, retrieve
from src.self_check import self_check

logger = logging.getLogger(__name__)

_REJECT_ANSWER = "根据提供的文档，无法找到相关信息。"
_WARN_LABEL = " ⚠️ [低置信度，请核实来源]"

_kb = None


def _get_kb():
    global _kb
    if _kb is None:
        persist_dir = Path(cfg.get("paths", {}).get("chroma_db", "data/chroma_db"))
        _kb = load_knowledge_base(persist_dir)
    return _kb


def ask(question: str) -> dict:
    """
    End-to-end RAG Q&A with self-check.

    Returns:
        {
            "question": str,
            "answer": str,
            "sources": list[dict],
            "self_check": {"verdict": str, "reason": str, "action": str}
        }
    """
    kb = _get_kb()

    docs = retrieve(question, kb)
    prompt = build_prompt(question, docs)
    answer = generate_answer(prompt)
    sources = format_sources(docs)

    check_result = self_check(question, answer, sources)

    action = check_result.get("action", "answer")
    if action == "reject":
        answer = _REJECT_ANSWER
    elif action == "warn":
        answer = answer + _WARN_LABEL

    return {
        "question": question,
        "answer": answer,
        "sources": sources,
        "self_check": check_result,
    }
