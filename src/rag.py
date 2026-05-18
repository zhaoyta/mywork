"""
RAG core: retrieval, prompt building, answer generation, source formatting.
"""
from __future__ import annotations

import logging
import os
from typing import Any

from langchain_core.documents import Document

from src.config import cfg

logger = logging.getLogger(__name__)

_REJECT_ANSWER = "根据提供的文档，无法找到相关信息。"

_PROMPT_TEMPLATE = """\
你是一个专业的文档问答助手。请根据以下参考文档片段回答问题。
如果参考文档中没有相关信息，请直接回答"根据提供的文档，无法找到相关信息。"，不要编造答案。
回答使用中文，长度不超过 500 字。

参考文档：
{context}

问题：{question}

回答："""


def retrieve(question: str, kb: Any, top_k: int | None = None) -> list[Document]:
    """Vector-search the knowledge base; return top-k documents with scores."""
    k = top_k or cfg.get("retrieval", {}).get("top_k", 5)
    results = kb.similarity_search_with_score(question, k=k)
    docs = []
    for doc, score in results:
        doc.metadata["score"] = float(score)
        docs.append(doc)
    logger.info("Retrieved %d docs for question: %s", len(docs), question[:50])
    return docs


def build_prompt(question: str, retrieved_docs: list[Document]) -> str:
    """Assemble the RAG prompt from retrieved documents."""
    if not retrieved_docs:
        return _REJECT_ANSWER

    context_parts = []
    for i, doc in enumerate(retrieved_docs, start=1):
        meta = doc.metadata
        header = f"[片段{i} | 第{meta.get('page', '?')}页 | {meta.get('type', 'text')}]"
        context_parts.append(f"{header}\n{doc.page_content}")

    context = "\n\n".join(context_parts)
    return _PROMPT_TEMPLATE.format(context=context, question=question)


def _get_llm() -> Any:
    """Return a LangChain LLM instance."""
    from langchain_openai import ChatOpenAI

    model = os.getenv("LLM_MODEL", "gpt-4o-mini")
    api_key = os.getenv("OPENAI_API_KEY", "")
    base_url = os.getenv("OPENAI_BASE_URL")
    kwargs: dict = {"model": model, "api_key": api_key, "temperature": 0}
    if base_url:
        kwargs["base_url"] = base_url
    return ChatOpenAI(**kwargs)


def generate_answer(prompt: str) -> str:
    """Call LLM with the given prompt. Returns _REJECT_ANSWER if prompt is itself the reject."""
    if prompt == _REJECT_ANSWER:
        return _REJECT_ANSWER

    llm = _get_llm()
    response = llm.invoke(prompt)
    answer = response.content if hasattr(response, "content") else str(response)
    logger.info("Generated answer (%d chars)", len(answer))
    return answer.strip()


def format_sources(docs: list[Document]) -> list[dict]:
    """Format retrieved docs into a compact source list."""
    sources = []
    for doc in docs:
        meta = doc.metadata
        snippet = doc.page_content[:50].replace("\n", " ")
        sources.append({
            "page": meta.get("page"),
            "type": meta.get("type", "text"),
            "snippet": snippet,
            "score": meta.get("score"),
        })
    return sources
