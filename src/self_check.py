"""
Answer self-check: ask the LLM whether the answer is supported by retrieved sources.
"""
from __future__ import annotations

import json
import logging
import os
import signal
from typing import Any

from src.config import cfg

logger = logging.getLogger(__name__)

_FALLBACK = {"verdict": "uncertain", "reason": "self_check_failed", "action": "warn"}

_SELF_CHECK_PROMPT = """\
你是一个严格的答案核查员。请判断以下"答案"是否有充分依据来自"参考片段"。

问题：{question}

参考片段：
{sources}

答案：{answer}

请以 JSON 格式输出，不要加任何额外文字：
{{
  "verdict": "supported" | "uncertain" | "unsupported",
  "reason": "<简短说明，50字以内>",
  "action": "answer" | "warn" | "reject"
}}

规则：
- supported + answer：答案有明确依据
- uncertain + warn：答案部分推断或依据薄弱
- unsupported + reject：答案与参考片段无关或明显捏造"""


class _TimeoutError(Exception):
    pass


def _timeout_handler(signum: int, frame: Any) -> None:
    raise _TimeoutError()


def self_check(question: str, answer: str, sources: list[dict]) -> dict:
    """
    Call LLM to verify whether the answer is grounded in the retrieved sources.

    Returns a dict with keys: verdict, reason, action.
    On timeout or any error, returns the fallback 'uncertain/warn' dict.
    """
    if not cfg.get("self_check", {}).get("enabled", True):
        return {"verdict": "supported", "reason": "self_check_disabled", "action": "answer"}

    timeout_sec = int(cfg.get("self_check", {}).get("timeout", 10))

    sources_text = "\n".join(
        f"[第{s.get('page', '?')}页] {s.get('snippet', '')}" for s in sources
    )
    prompt = _SELF_CHECK_PROMPT.format(
        question=question,
        sources=sources_text or "(无检索结果)",
        answer=answer,
    )

    # Use SIGALRM on Unix for timeout; fallback gracefully on Windows
    use_signal = hasattr(signal, "SIGALRM")
    try:
        if use_signal:
            signal.signal(signal.SIGALRM, _timeout_handler)
            signal.alarm(timeout_sec)

        result = _call_llm(prompt)

        if use_signal:
            signal.alarm(0)

        return result
    except _TimeoutError:
        logger.warning("self_check timed out after %ds", timeout_sec)
        return _FALLBACK
    except Exception as exc:
        logger.warning("self_check failed: %s", exc)
        if use_signal:
            signal.alarm(0)
        return _FALLBACK


def _call_llm(prompt: str) -> dict:
    """Call LLM and parse JSON response."""
    from langchain_openai import ChatOpenAI

    model = os.getenv("LLM_MODEL", "gpt-4o-mini")
    api_key = os.getenv("OPENAI_API_KEY", "")
    base_url = os.getenv("OPENAI_BASE_URL")
    kwargs: dict = {"model": model, "api_key": api_key, "temperature": 0}
    if base_url:
        kwargs["base_url"] = base_url

    llm = ChatOpenAI(**kwargs)
    response = llm.invoke(prompt)
    raw = response.content if hasattr(response, "content") else str(response)

    return _parse_json(raw)


def _parse_json(raw: str) -> dict:
    """Parse JSON from LLM output; fall back to uncertain on failure."""
    raw = raw.strip()
    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    try:
        data = json.loads(raw)
        verdict = data.get("verdict", "uncertain")
        action = data.get("action", "warn")
        reason = data.get("reason", "")

        # Validate enum values
        if verdict not in ("supported", "uncertain", "unsupported"):
            verdict = "uncertain"
        if action not in ("answer", "warn", "reject"):
            action = "warn"

        return {"verdict": verdict, "reason": reason, "action": action}
    except (json.JSONDecodeError, KeyError) as exc:
        logger.warning("self_check JSON parse failed: %s | raw=%s", exc, raw[:100])
        return _FALLBACK
