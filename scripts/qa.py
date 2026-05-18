"""
Single-question CLI.

Usage:
    uv run python scripts/qa.py --question "键的材料硬度要求是什么？"
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import cfg

logging.basicConfig(
    level=cfg.get("logging", {}).get("level", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

from src.agent import ask


def main() -> None:
    parser = argparse.ArgumentParser(description="Ask a question about the ingested document")
    parser.add_argument("--question", "-q", required=True, help="Question to ask")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    args = parser.parse_args()

    result = ask(args.question)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    print(f"\n问题：{result['question']}")
    print(f"\n答案：{result['answer']}")

    check = result["self_check"]
    verdict_icon = {"supported": "✓", "uncertain": "⚠", "unsupported": "✗"}.get(
        check.get("verdict", ""), "?"
    )
    print(f"\n自检：{verdict_icon} {check.get('verdict')} — {check.get('reason', '')}")

    if result["sources"]:
        print("\n来源：")
        for s in result["sources"]:
            print(f"  第{s['page']}页 [{s['type']}] {s['snippet']}...")


if __name__ == "__main__":
    main()
