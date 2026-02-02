#!/usr/bin/env python3
"""Calculate DocILE accuracy metrics for all baselines.

This script parses result files and calculates field-level accuracy
for KILE (Key Information Extraction) and LIR (Line Item Recognition) tasks.
"""

import json
import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any


# KILE fields we evaluate (matching paper)
KILE_FIELDS = [
    "document_id",
    "vendor_name",
    "customer_name",
    "invoice_date",
    "due_date",
    "total_amount",
    "tax_amount",
    "currency",
]

# LIR fields we evaluate
LIR_FIELDS = ["description", "quantity", "unit_price", "total_price"]


@dataclass
class FieldAccuracy:
    """Track accuracy for a single field."""
    correct: int = 0
    incorrect: int = 0
    missing_pred: int = 0
    missing_gt: int = 0

    @property
    def total(self) -> int:
        return self.correct + self.incorrect + self.missing_pred

    @property
    def accuracy(self) -> float:
        if self.total == 0:
            return 0.0
        return self.correct / self.total


@dataclass
class BaselineResult:
    """Results for a single baseline."""
    name: str
    task: str  # "kile" or "lir"
    instances: int = 0
    field_accuracies: dict[str, FieldAccuracy] = field(default_factory=dict)
    avg_latency_ms: float = 0.0

    @property
    def overall_accuracy(self) -> float:
        """Calculate overall accuracy across all fields."""
        total_correct = sum(fa.correct for fa in self.field_accuracies.values())
        total_evaluated = sum(fa.total for fa in self.field_accuracies.values())
        if total_evaluated == 0:
            return 0.0
        return total_correct / total_evaluated


def normalize_value(val: Any) -> str:
    """Normalize a value for comparison."""
    if val is None:
        return ""

    # Convert to string
    s = str(val).strip()

    # Remove currency symbols and commas for amounts
    s = re.sub(r'[$€£¥,]', '', s)

    # Normalize whitespace
    s = ' '.join(s.split())

    # Lowercase for comparison
    s = s.lower()

    return s


def parse_output(output: str) -> dict | list | None:
    """Parse JSON output, handling markdown code blocks."""
    if not output:
        return None

    # Remove markdown code blocks
    output = re.sub(r'^```(?:json)?\s*\n?', '', output.strip())
    output = re.sub(r'\n?```\s*$', '', output.strip())

    try:
        return json.loads(output)
    except json.JSONDecodeError:
        # Try to extract JSON from the output
        match = re.search(r'\{[^{}]*\}|\[[^\[\]]*\]', output, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    return None


def compare_kile_fields(predicted: dict, expected: dict, field_accuracies: dict[str, FieldAccuracy]):
    """Compare KILE fields and update accuracy counters."""
    for field_name in KILE_FIELDS:
        if field_name not in field_accuracies:
            field_accuracies[field_name] = FieldAccuracy()

        fa = field_accuracies[field_name]

        pred_val = normalize_value(predicted.get(field_name))
        exp_val = normalize_value(expected.get(field_name))

        # Skip if no ground truth
        if not exp_val:
            fa.missing_gt += 1
            continue

        # Check if prediction is missing
        if not pred_val:
            fa.missing_pred += 1
            continue

        # Compare values (fuzzy match)
        if values_match(pred_val, exp_val):
            fa.correct += 1
        else:
            fa.incorrect += 1


def values_match(pred: str, exp: str) -> bool:
    """Check if two values match (with some tolerance)."""
    if pred == exp:
        return True

    # Check if one contains the other
    if pred in exp or exp in pred:
        return True

    # Try numeric comparison for amounts
    try:
        pred_num = float(re.sub(r'[^\d.]', '', pred))
        exp_num = float(re.sub(r'[^\d.]', '', exp))
        if abs(pred_num - exp_num) < 0.01:
            return True
    except (ValueError, TypeError):
        pass

    return False


def compare_lir_items(predicted: list, expected: list, field_accuracies: dict[str, FieldAccuracy]):
    """Compare LIR line items and update accuracy counters."""
    for field_name in LIR_FIELDS:
        if field_name not in field_accuracies:
            field_accuracies[field_name] = FieldAccuracy()

    # Match predicted items to expected items by description similarity
    pred_items = predicted if isinstance(predicted, list) else []
    exp_items = expected if isinstance(expected, list) else []

    # Simple matching: compare each expected item against all predicted items
    for exp_item in exp_items:
        exp_dict = exp_item if isinstance(exp_item, dict) else {}

        # Find best matching predicted item
        best_match = None
        best_score = 0

        for pred_item in pred_items:
            pred_dict = pred_item if isinstance(pred_item, dict) else {}
            score = item_similarity(pred_dict, exp_dict)
            if score > best_score:
                best_score = score
                best_match = pred_dict

        # Update field accuracies
        for field_name in LIR_FIELDS:
            fa = field_accuracies[field_name]

            exp_val = normalize_value(exp_dict.get(field_name) or exp_dict.get("amount" if field_name == "total_price" else field_name))

            if not exp_val:
                fa.missing_gt += 1
                continue

            if best_match is None:
                fa.missing_pred += 1
                continue

            pred_val = normalize_value(best_match.get(field_name) or best_match.get("amount" if field_name == "total_price" else field_name))

            if not pred_val:
                fa.missing_pred += 1
            elif values_match(pred_val, exp_val):
                fa.correct += 1
            else:
                fa.incorrect += 1


def item_similarity(pred: dict, exp: dict) -> float:
    """Calculate similarity between two line items."""
    score = 0
    for field in LIR_FIELDS:
        pred_val = normalize_value(pred.get(field) or pred.get("amount" if field == "total_price" else field))
        exp_val = normalize_value(exp.get(field) or exp.get("amount" if field == "total_price" else field))
        if pred_val and exp_val and values_match(pred_val, exp_val):
            score += 1
    return score


def process_result_file(filepath: Path, task: str) -> BaselineResult | None:
    """Process a single result file and return accuracy metrics."""
    try:
        with open(filepath) as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return None

    # Extract baseline name
    config = data.get("config", {})
    baseline_name = config.get("baseline", filepath.stem.split("_")[0])

    # Get instances from logs
    logs = data.get("logs", [])
    if not logs or "instances" not in logs[0]:
        print(f"No instances in {filepath}")
        return None

    instances = logs[0].get("instances", [])

    result = BaselineResult(
        name=baseline_name,
        task=task,
        instances=len(instances),
    )

    total_latency = 0.0

    for inst in instances:
        # Parse output and expected
        output_str = inst.get("output", "")
        expected = inst.get("expected_output")

        predicted = parse_output(output_str)

        if task == "kile":
            pred_dict = predicted if isinstance(predicted, dict) else {}
            exp_dict = expected if isinstance(expected, dict) else {}
            compare_kile_fields(pred_dict, exp_dict, result.field_accuracies)
        else:  # lir
            pred_list = predicted.get("line_items", predicted) if isinstance(predicted, dict) else (predicted if isinstance(predicted, list) else [])
            exp_list = expected if isinstance(expected, list) else []
            compare_lir_items(pred_list, exp_list, result.field_accuracies)

        total_latency += inst.get("latency_ms", 0)

    if result.instances > 0:
        result.avg_latency_ms = total_latency / result.instances

    return result


def process_code_factory_progress(filepath: Path, task: str, gt_dir: Path) -> BaselineResult | None:
    """Process Code Factory progress file."""
    try:
        with open(filepath) as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return None

    completed = data.get("completed", {})

    result = BaselineResult(
        name="code_factory",
        task=task,
        instances=len(completed),
    )

    total_latency = 0.0

    # Load ground truth from annotations
    converter_map = {
        "document_id": ["document_id", "invoice_id", "invoice_number"],
        "vendor_name": ["vendor_name"],
        "customer_name": ["customer_name", "customer_billing_name", "customer_shipping_name"],
        "invoice_date": ["date_issue", "invoice_date"],
        "due_date": ["date_due", "due_date"],
        "total_amount": ["amount_total_gross", "total_amount", "amount_due"],
        "tax_amount": ["tax_amount", "tax"],
        "currency": ["currency", "currency_code", "currency_code_amount_due"],
    }

    for doc_id, doc_data in completed.items():
        # Load ground truth
        ann_path = gt_dir / "annotations" / f"{doc_id}.json"
        if not ann_path.exists():
            continue

        with open(ann_path) as f:
            annotation = json.load(f)

        # Parse output
        output_str = doc_data.get("output", "")
        predicted = parse_output(output_str)

        if task == "kile":
            # Extract expected from annotation
            expected = {}
            for field_ext in annotation.get("field_extractions", []):
                field_type = field_ext.get("fieldtype", "")
                value = field_ext.get("text", "")
                for kile_field, docile_fields in converter_map.items():
                    if field_type in docile_fields and kile_field not in expected:
                        expected[kile_field] = value

            pred_dict = predicted if isinstance(predicted, dict) else {}
            compare_kile_fields(pred_dict, expected, result.field_accuracies)
        else:  # lir
            # Extract expected line items
            expected = []
            items_by_id = {}
            for item in annotation.get("line_item_extractions", []):
                line_id = str(item.get("line_item_id", ""))
                if not line_id:
                    continue
                entry = items_by_id.setdefault(line_id, {})
                field_type = item.get("fieldtype", "").lower()
                value = item.get("text", "")

                if "description" in field_type or field_type in ("item", "name"):
                    entry["description"] = value
                elif "qty" in field_type or "quantity" in field_type:
                    entry["quantity"] = value
                elif "unit_price" in field_type:
                    entry["unit_price"] = value
                elif "amount" in field_type or "total" in field_type:
                    entry["total_price"] = value

            expected = list(items_by_id.values())

            pred_list = predicted.get("line_items", predicted) if isinstance(predicted, dict) else (predicted if isinstance(predicted, list) else [])
            compare_lir_items(pred_list, expected, result.field_accuracies)

        total_latency += doc_data.get("latency_s", 0) * 1000

    if result.instances > 0:
        result.avg_latency_ms = total_latency / result.instances

    return result


def print_results(results: list[BaselineResult], task: str):
    """Print results in a formatted table."""
    fields = KILE_FIELDS if task == "kile" else LIR_FIELDS

    print(f"\n{'='*80}")
    print(f"DocILE {task.upper()} Accuracy Results (n={results[0].instances if results else 0})")
    print(f"{'='*80}")

    # Header
    print(f"\n{'Baseline':<15} {'Overall':>10}", end="")
    for field in fields:
        short_name = field[:8]
        print(f" {short_name:>10}", end="")
    print(f" {'Latency':>10}")

    print("-" * (30 + len(fields) * 11 + 11))

    for result in results:
        print(f"{result.name:<15} {result.overall_accuracy*100:>9.1f}%", end="")
        for field in fields:
            fa = result.field_accuracies.get(field, FieldAccuracy())
            print(f" {fa.accuracy*100:>9.1f}%", end="")
        print(f" {result.avg_latency_ms:>9.0f}ms")

    print()


def main():
    results_dir = Path("/Users/geerttrooskens/dev/xy/CompiledAI/results")
    gt_dir = Path("/Users/geerttrooskens/dev/xy/CompiledAI/datasets/benchmarks/DocILE")

    # Find and process result files
    kile_results = []
    lir_results = []

    # Process standard baseline result files
    baselines = ["direct_llm", "langchain", "autogen"]

    for baseline in baselines:
        # KILE
        kile_files = list(results_dir.glob(f"{baseline}_docile_kile_*.json"))
        if kile_files:
            # Use the most recent file
            kile_file = max(kile_files, key=lambda p: p.stat().st_mtime)
            result = process_result_file(kile_file, "kile")
            if result:
                kile_results.append(result)

        # LIR
        lir_files = list(results_dir.glob(f"{baseline}_docile_lir_*.json"))
        if lir_files:
            lir_file = max(lir_files, key=lambda p: p.stat().st_mtime)
            result = process_result_file(lir_file, "lir")
            if result:
                lir_results.append(result)

    # Process Code Factory progress files
    kile_progress = results_dir / "docile_code_factory_progress.json"
    if kile_progress.exists():
        result = process_code_factory_progress(kile_progress, "kile", gt_dir)
        if result:
            kile_results.append(result)

    lir_progress = results_dir / "docile_code_factory_lir_progress.json"
    if lir_progress.exists():
        result = process_code_factory_progress(lir_progress, "lir", gt_dir)
        if result:
            lir_results.append(result)

    # Print results
    if kile_results:
        print_results(kile_results, "kile")

    if lir_results:
        print_results(lir_results, "lir")

    # Print summary table matching paper format
    print("\n" + "="*80)
    print("Summary Table (Paper Format)")
    print("="*80)
    print(f"\n{'Approach':<15} {'KILE Acc.':>12} {'LIR Acc.':>12} {'Latency':>12}")
    print("-"*55)

    # Match baselines
    baseline_names = ["direct_llm", "langchain", "autogen", "code_factory"]
    display_names = ["Direct LLM", "LangChain", "AutoGen", "Code Factory"]

    for name, display in zip(baseline_names, display_names):
        kile_acc = next((r.overall_accuracy for r in kile_results if r.name == name), None)
        lir_acc = next((r.overall_accuracy for r in lir_results if r.name == name), None)
        kile_lat = next((r.avg_latency_ms for r in kile_results if r.name == name), None)

        kile_str = f"{kile_acc*100:.1f}%" if kile_acc is not None else "N/A"
        lir_str = f"{lir_acc*100:.1f}%" if lir_acc is not None else "N/A"
        lat_str = f"{kile_lat:,.0f} ms" if kile_lat is not None else "N/A"

        print(f"{display:<15} {kile_str:>12} {lir_str:>12} {lat_str:>12}")


if __name__ == "__main__":
    main()
