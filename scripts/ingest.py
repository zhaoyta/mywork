"""
Ingest a PDF into the knowledge base.

Usage:
    uv run python scripts/ingest.py --pdf data/pdfs/xxx.pdf [--force]
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# ensure src/ is importable when run as a script
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import cfg
from src.knowledge_base import build_knowledge_base, load_knowledge_base, split_chunks
from src.pdf_parser import parse_pdf

logging.basicConfig(
    level=cfg.get("logging", {}).get("level", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("ingest")


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest PDF into knowledge base")
    parser.add_argument("--pdf", required=True, help="Path to the PDF file")
    parser.add_argument("--force", action="store_true", help="Force rebuild even if KB exists")
    args = parser.parse_args()

    persist_dir = Path(cfg.get("paths", {}).get("chroma_db", "data/chroma_db"))

    if persist_dir.exists() and any(persist_dir.iterdir()) and not args.force:
        logger.info("Knowledge base already exists. Use --force to rebuild.")
        load_knowledge_base(persist_dir)
        return

    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        logger.error("PDF not found: %s", pdf_path)
        sys.exit(1)

    logger.info("Parsing PDF: %s", pdf_path)
    blocks = parse_pdf(pdf_path)

    text_blocks = [b for b in blocks if b["type"] == "text"]
    table_blocks = [b for b in blocks if b["type"] == "table"]
    pages = max((b["page"] for b in blocks), default=0)

    logger.info("Splitting into chunks...")
    chunks = split_chunks(blocks)

    persist_dir.mkdir(parents=True, exist_ok=True)
    build_knowledge_base(chunks, persist_dir)

    print(
        f"[Ingest] total={len(chunks)}, "
        f"text={len(text_blocks)}, "
        f"table={len(table_blocks)}, "
        f"pages={pages}"
    )


if __name__ == "__main__":
    main()
