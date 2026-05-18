"""
Evaluation script: batch Q&A over test_cases.json, compute metrics, write report.

Usage:
    uv run python tests/evaluate.py
    uv run python tests/evaluate.py --baseline tests/results/baseline.json
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import cfg

logging.basicConfig(
    level=cfg.get("logging", {}).get("level", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("evaluate")

TEST_CASES_PATH = Path(__file__).parent / "test_cases.json"
RESULTS_DIR = Path(__file__).parent / "results"


def _load_test_cases() -> list[dict]:
    with open(TEST_CASES_PATH, encoding="utf-8") as f:
        return json.load(f)


def _run_case(case: dict) -> dict:
    from src.agent import ask

    question = case["question"]
    result = ask(question)

    answer = result["answer"]
    sources = result["sources"]
    check = result["self_check"]

    # Determine hit
    expect_reject = case.get("expect_reject", False)
    keywords = case.get("expected_keywords", [])

    if expect_reject:
        hit = check.get("action") == "reject" or "无法找到" in answer
    else:
        hit = all(kw in answer for kw in keywords) if keywords else True

    # Source page hit: any source page returned
    source_hit = len(sources) > 0

    return {
        "id": case["id"],
        "category": case["category"],
        "question": question,
        "answer": answer,
        "sources": sources,
        "self_check": check,
        "hit": hit,
        "source_hit": source_hit,
        "expect_reject": expect_reject,
    }


def _compute_metrics(records: list[dict]) -> dict:
    categories = {}
    for r in records:
        cat = r["category"]
        categories.setdefault(cat, {"total": 0, "hit": 0})
        categories[cat]["total"] += 1
        if r["hit"]:
            categories[cat]["hit"] += 1

    overall_hit = sum(1 for r in records if r["hit"]) / len(records) if records else 0
    reject_cases = [r for r in records if r["expect_reject"]]
    reject_acc = (
        sum(1 for r in reject_cases if r["hit"]) / len(reject_cases) if reject_cases else None
    )
    source_acc = sum(1 for r in records if r["source_hit"]) / len(records) if records else 0

    per_category = {
        cat: round(v["hit"] / v["total"], 3) if v["total"] else 0
        for cat, v in categories.items()
    }

    return {
        "overall_hit_rate": round(overall_hit, 3),
        "reject_accuracy": round(reject_acc, 3) if reject_acc is not None else None,
        "source_page_accuracy": round(source_acc, 3),
        "per_category": per_category,
    }


def _compare_baseline(current: dict, baseline: dict) -> list[str]:
    regressions = []
    cur_cat = current.get("per_category", {})
    base_cat = baseline.get("summary", {}).get("per_category", {})
    for cat, base_val in base_cat.items():
        cur_val = cur_cat.get(cat, 0)
        if base_val - cur_val > 0.10:
            regressions.append(
                f"REGRESSION [{cat}]: {base_val:.1%} → {cur_val:.1%} (drop {base_val - cur_val:.1%})"
            )
    return regressions


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate the Q&A agent")
    parser.add_argument("--baseline", help="Path to baseline JSON for regression comparison")
    args = parser.parse_args()

    cases = _load_test_cases()
    logger.info("Running %d test cases...", len(cases))

    records = []
    for case in cases:
        logger.info("  [%s] %s", case["id"], case["question"])
        try:
            record = _run_case(case)
        except Exception as exc:
            logger.error("  FAILED %s: %s", case["id"], exc)
            record = {**case, "answer": f"ERROR: {exc}", "sources": [], "self_check": {}, "hit": False, "source_hit": False}
        records.append(record)
        status = "✓" if record["hit"] else "✗"
        print(f"  {status} [{case['id']}] {case['question'][:40]}...")

    metrics = _compute_metrics(records)

    print("\n── Evaluation Summary ──")
    print(f"  Overall hit rate : {metrics['overall_hit_rate']:.1%}")
    print(f"  Reject accuracy  : {metrics['reject_accuracy']:.1%}" if metrics["reject_accuracy"] is not None else "  Reject accuracy  : N/A")
    print(f"  Source page acc  : {metrics['source_page_accuracy']:.1%}")
    print("  Per category:")
    for cat, rate in metrics["per_category"].items():
        print(f"    {cat:<12}: {rate:.1%}")

    # Write report
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = RESULTS_DIR / "eval_report.json"
    report = {
        "timestamp": datetime.now().isoformat(),
        "summary": metrics,
        "records": records,
    }
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\nReport written to {report_path}")

    # Baseline comparison
    if args.baseline:
        baseline_path = Path(args.baseline)
        if not baseline_path.exists():
            print(f"Baseline not found: {baseline_path}")
            sys.exit(1)
        with open(baseline_path, encoding="utf-8") as f:
            baseline = json.load(f)
        regressions = _compare_baseline(metrics, baseline)
        if regressions:
            print("\n⚠️  REGRESSIONS DETECTED:")
            for r in regressions:
                print(f"  {r}")
            sys.exit(1)
        else:
            print("\n✓ No regressions vs baseline.")


if __name__ == "__main__":
    main()
