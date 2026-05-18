"""
Knowledge base: chunking, embedding, ChromaDB persistence.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.config import cfg

logger = logging.getLogger(__name__)

_COLLECTION_NAME = "doc_qa"


def split_chunks(blocks: list[dict]) -> list[Document]:
    """
    Split text blocks with RecursiveCharacterTextSplitter.
    Table blocks are kept as-is (not split).
    """
    chunk_cfg = cfg.get("chunking", {})
    chunk_size = int(chunk_cfg.get("chunk_size", 500))
    chunk_overlap = int(chunk_cfg.get("chunk_overlap", 100))
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", "。", "；", " ", ""],
    )

    docs: list[Document] = []
    for block in blocks:
        meta = {
            "page": block["page"],
            "type": block["type"],
            "source": block["source"],
            "clause_id": block.get("clause_id", ""),
        }
        if block["type"] == "table":
            docs.append(Document(page_content=block["content"], metadata=meta))
        else:
            sub = splitter.create_documents([block["content"]], metadatas=[meta])
            docs.extend(sub)

    logger.info("split_chunks: %d blocks → %d chunks", len(blocks), len(docs))
    return docs


def get_embedder() -> Any:
    """
    Return an embedding model.
    Priority: OpenAI → local bge-small-zh-v1.5.
    """
    api_key = os.getenv("OPENAI_API_KEY", "")
    embed_model = os.getenv("EMBED_MODEL", "text-embedding-3-small")

    if api_key and embed_model != "local":
        from langchain_openai import OpenAIEmbeddings

        base_url = os.getenv("OPENAI_BASE_URL")
        logger.info("Using OpenAI embeddings: %s", embed_model)
        kwargs: dict = {"model": embed_model, "api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        return OpenAIEmbeddings(**kwargs)

    local_model = os.getenv("LOCAL_EMBED_MODEL", "BAAI/bge-small-zh-v1.5")
    logger.info("Falling back to local embeddings: %s", local_model)
    from langchain_community.embeddings import HuggingFaceEmbeddings

    return HuggingFaceEmbeddings(
        model_name=local_model,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )


def build_knowledge_base(chunks: list[Document], persist_dir: str | Path) -> Any:
    """Embed chunks and persist to ChromaDB. Returns the Chroma vectorstore."""
    from langchain_chroma import Chroma

    persist_dir = str(persist_dir)
    embedder = get_embedder()
    logger.info("Building knowledge base with %d chunks → %s", len(chunks), persist_dir)
    vectorstore = Chroma.from_documents(
        documents=chunks,
        embedding=embedder,
        collection_name=_COLLECTION_NAME,
        persist_directory=persist_dir,
    )
    logger.info("Knowledge base built and persisted.")
    return vectorstore


def load_knowledge_base(persist_dir: str | Path) -> Any:
    """Load existing ChromaDB vectorstore and log chunk count."""
    from langchain_chroma import Chroma

    persist_dir = str(persist_dir)
    embedder = get_embedder()
    vectorstore = Chroma(
        collection_name=_COLLECTION_NAME,
        embedding_function=embedder,
        persist_directory=persist_dir,
    )
    count = vectorstore._collection.count()
    logger.info("Loaded knowledge base from %s: %d chunks", persist_dir, count)
    print(f"[KnowledgeBase] Loaded {count} chunks from {persist_dir}")
    return vectorstore
