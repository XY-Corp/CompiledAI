#!/usr/bin/env python3
"""Evaluate Code Factory DocILE outputs using LLM evaluator.

This script runs the same LLM-based evaluation used for other baselines
on the Code Factory progress files.
"""

import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from compiled_ai.evaluation import LLMEvaluator
from compiled_ai.datasets.docile_converter import DocILEConverter


def load_ground_truth(gt_dir: Path, doc_id: str, task: str) -> dict | list:
    """Load ground truth from DocILE annotations."""
    converter = DocILEConverter()
    ann_path = gt_dir / "annotations" / f"{doc_id}.json"

    if not ann_path.exists():
        return {} if task == "kile" else []

    with open(ann_path) as f:
        annotation = json.load(f)

    if task == "kile":
        return converter._extract_kile_fields(annotation)
    else:
        return converter._extract_line_items(annotation)


def build_output_format(task: str) -> dict:
    """Build output format for evaluation."""
    if task == "kile":
        return {
            "type": "object",
            "fields": {
                "document_id": "string - invoice/document ID",
                "vendor_name": "string - vendor/seller name",
                "customer_name": "string - customer/buyer name",
                "invoice_date": "string - invoice date",
                "due_date": "string - payment due date",
                "total_amount": "number - total amount",
                "tax_amount": "number - tax amount",
                "currency": "string - currency code",
            },
        }
    else:
        return {
            "type": "array",
            "items": {
                "type": "object",
                "fields": {
                    "description": "string - line item description",
                    "quantity": "number - quantity",
                    "unit_price": "number - unit price",
                    "total_price": "number - line total",
                },
            },
        }


def evaluate_progress_file(progress_path: Path, gt_dir: Path, task: str, max_docs: int = 100) -> tuple[float, float, int]:
    """Evaluate a Code Factory progress file.

    Returns:
        Tuple of (mean_score, mean_latency_ms, count)
    """
    with open(progress_path) as f:
        data = json.load(f)

    completed = data.get("completed", {})
    evaluator = LLMEvaluator()
    output_format = build_output_format(task)

    scores = []
    latencies = []

    doc_ids = list(completed.keys())[:max_docs]

    for i, doc_id in enumerate(doc_ids):
        doc_data = completed[doc_id]

        # Get ground truth
        expected = load_ground_truth(gt_dir, doc_id, task)

        # Get prediction
        output = doc_data.get("output", "")

        # Run evaluation
        try:
            result = evaluator.evaluate(
                output=output,
                expected=expected,
                output_format=output_format,
            )
            scores.append(result.score)
            print(f"  [{i+1}/{len(doc_ids)}] {doc_id}: score={result.score:.2f}, match_type={result.details.get('match_type', 'unknown')}")
        except Exception as e:
            print(f"  [{i+1}/{len(doc_ids)}] {doc_id}: ERROR - {e}")
            scores.append(0.0)

        latencies.append(doc_data.get("latency_s", 0) * 1000)

    mean_score = sum(scores) / len(scores) if scores else 0
    mean_latency = sum(latencies) / len(latencies) if latencies else 0

    return mean_score, mean_latency, len(scores)


def main():
    results_dir = Path("/Users/geerttrooskens/dev/xy/CompiledAI/results")
    gt_dir = Path("/Users/geerttrooskens/dev/xy/CompiledAI/datasets/benchmarks/DocILE")

    print("="*70)
    print("Evaluating Code Factory DocILE Outputs")
    print("="*70)

    results = {}

    # Evaluate KILE
    kile_progress = results_dir / "docile_code_factory_progress.json"
    if kile_progress.exists():
        print(f"\nEvaluating KILE ({kile_progress.name})...")
        score, latency, count = evaluate_progress_file(kile_progress, gt_dir, "kile", max_docs=100)
        results["KILE"] = (score, latency, count)
        print(f"\nKILE Results: score={score*100:.1f}%, latency={latency:,.0f}ms, n={count}")
    else:
        print(f"KILE progress file not found: {kile_progress}")

    # Evaluate LIR
    lir_progress = results_dir / "docile_code_factory_lir_progress.json"
    if lir_progress.exists():
        print(f"\nEvaluating LIR ({lir_progress.name})...")
        score, latency, count = evaluate_progress_file(lir_progress, gt_dir, "lir", max_docs=100)
        results["LIR"] = (score, latency, count)
        print(f"\nLIR Results: score={score*100:.1f}%, latency={latency:,.0f}ms, n={count}")
    else:
        print(f"LIR progress file not found: {lir_progress}")

    # Summary
    print("\n" + "="*70)
    print("Code Factory Summary")
    print("="*70)

    if "KILE" in results:
        kile_score, kile_lat, kile_n = results["KILE"]
        print(f"KILE: {kile_score*100:.1f}% (n={kile_n}, latency={kile_lat:,.0f}ms)")

    if "LIR" in results:
        lir_score, lir_lat, lir_n = results["LIR"]
        print(f"LIR: {lir_score*100:.1f}% (n={lir_n}, latency={lir_lat:,.0f}ms)")


if __name__ == "__main__":
    main()
