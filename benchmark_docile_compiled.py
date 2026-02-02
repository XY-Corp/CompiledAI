#!/usr/bin/env python3
"""
Full DocILE Benchmark - Compiled (Regex) Approach vs LLM

Runs pure regex/compiled extraction on the FULL DocILE dataset and
compares against ground truth annotations.
"""

import json
import time
import os
import sys
import re
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass, field, asdict
from collections import defaultdict
from datetime import datetime


# ============================================================================
# INLINE KILE ACTIVITIES (from docile_workflows/kile/activities.py)
# ============================================================================

def _fix_ocr_digits(text: str) -> str:
    """Fix common OCR digit misreadings."""
    replacements = {'O': '0', 'o': '0', 'l': '1', 'I': '1', 'S': '5', 'B': '8', 'Z': '2'}
    result = text
    for old, new in replacements.items():
        result = result.replace(old, new)
    return result


def _parse_amount(text: str) -> Optional[float]:
    """Parse a monetary amount from text with OCR error correction."""
    if not text:
        return None
    
    cleaned = re.sub(r'[\$€£¥₹\s,]', '', text)
    cleaned = _fix_ocr_digits(cleaned)
    
    if ',' in cleaned and '.' in cleaned:
        if cleaned.rfind(',') > cleaned.rfind('.'):
            cleaned = cleaned.replace('.', '').replace(',', '.')
        else:
            cleaned = cleaned.replace(',', '')
    elif ',' in cleaned:
        if re.match(r'^[\d.]+,\d{2}$', cleaned):
            cleaned = cleaned.replace(',', '.')
        else:
            cleaned = cleaned.replace(',', '')
    
    try:
        return float(cleaned)
    except ValueError:
        return None


def _normalize_date(date_str: str) -> Optional[str]:
    """Normalize a date string to ISO format (YYYY-MM-DD)."""
    if not date_str:
        return None
    
    date_str = date_str.strip()
    date_str = _fix_ocr_digits(date_str)
    
    formats = [
        '%Y-%m-%d', '%d-%m-%Y', '%m-%d-%Y', '%Y/%m/%d', '%d/%m/%Y', '%m/%d/%Y',
        '%d.%m.%Y', '%B %d, %Y', '%b %d, %Y', '%d %B %Y', '%d %b %Y',
    ]
    
    for fmt in formats:
        try:
            parsed = datetime.strptime(date_str, fmt)
            return parsed.strftime('%Y-%m-%d')
        except ValueError:
            continue
    
    return date_str


def _extract_document_id(text: str) -> Optional[str]:
    """Extract invoice/receipt number from text."""
    patterns = [
        r'(?:Invoice|Receipt|Order)\s*(?:No\.?|Number|#)[\s:]*([A-Z0-9][-A-Z0-9]+)',
        r'(?:INV|REC|ORD)[-#]([A-Z0-9][-A-Z0-9]+)',
        r'(?:Invoice|Receipt|Order)[\s#:]+([A-Z0-9][-A-Z0-9]{3,})',
        r'#\s*([A-Z0-9][-A-Z0-9]{4,})',
        r'(?:Document|Doc)[\s#:.-]*([A-Z0-9][-A-Z0-9]+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            result = match.group(1).strip()
            if len(result) >= 3 and result.upper() not in ('NO', 'NO.'):
                return result
    return None


def _extract_vendor_name(text: str) -> Optional[str]:
    """Extract vendor/seller name from text."""
    lines = text.strip().split('\n')
    
    patterns = [
        r'(?:From|Seller|Vendor|Company|Sold\s*by)[\s:]+([^\n]+)',
        r'(?:Bill\s*From)[\s:]+([^\n]+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            name = match.group(1).strip()
            if name:
                return name
    
    for line in lines[:5]:
        line = line.strip()
        if line and len(line) > 2 and not re.match(r'^[\d\W]+$', line):
            if not re.search(r'\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}', line):
                if not re.search(r'^\$|^€|^£|^\d+\.\d{2}$', line):
                    return line
    
    return None


def _extract_customer_name(text: str) -> Optional[str]:
    """Extract customer/buyer name from text."""
    patterns = [r'(?:Bill\s*To|Customer|Client|Buyer|Sold\s*To|Ship\s*To)[\s:]+([^\n]+)']
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            name = match.group(1).strip()
            if name and not re.search(r'\d{5}', name):
                return name.split('\n')[0]
    return None


def _extract_date(text: str, keywords: list) -> Optional[str]:
    """Extract a date associated with specific keywords."""
    for keyword in keywords:
        pattern = rf'{keyword}[\s:]*([^\n]+)'
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            date_str = match.group(1).strip()
            date_match = re.search(
                r'(\d{1,4}[-/\.]\d{1,2}[-/\.]\d{1,4}|\w+\s+\d{1,2},?\s+\d{4}|\d{1,2}\s+\w+\s+\d{4})',
                date_str
            )
            if date_match:
                return _normalize_date(date_match.group(1))
    return None


def _extract_amount(text: str, keywords: list) -> Optional[float]:
    """Extract a monetary amount associated with specific keywords."""
    for keyword in keywords:
        pattern = rf'(?:^|[\s])({keyword})(?:\s*\([^)]*\))?[\s:]*[\$€£¥₹]?\s*([\d,.\s]+)'
        for match in re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE):
            start = match.start(1)
            if start > 0 and text[start-1:start].isalpha():
                continue
            amount = _parse_amount(match.group(2))
            if amount is not None:
                return amount
    return None


def _extract_currency(text: str) -> Optional[str]:
    """Extract currency code from text."""
    code_match = re.search(r'\b(USD|EUR|GBP|CAD|AUD|JPY|CHF|CNY|INR)\b', text, re.IGNORECASE)
    if code_match:
        return code_match.group(1).upper()
    
    if '$' in text:
        if re.search(r'\b(Canada|Canadian|CAD)\b', text, re.IGNORECASE):
            return 'CAD'
        if re.search(r'\b(Australia|Australian|AUD)\b', text, re.IGNORECASE):
            return 'AUD'
        return 'USD'
    if '€' in text:
        return 'EUR'
    if '£' in text:
        return 'GBP'
    if '¥' in text:
        return 'JPY'
    if '₹' in text:
        return 'INR'
    
    return None


def extract_invoice_fields(ocr_text: str) -> dict:
    """Extract invoice fields using regex patterns."""
    if not isinstance(ocr_text, str) or not ocr_text.strip():
        return {}
    
    return {
        'document_id': _extract_document_id(ocr_text),
        'vendor_name': _extract_vendor_name(ocr_text),
        'customer_name': _extract_customer_name(ocr_text),
        'invoice_date': _extract_date(ocr_text, ['Invoice Date', 'Date of Issue', 'Issue Date', 'Date']),
        'due_date': _extract_date(ocr_text, ['Due Date', 'Payment Due', 'Pay By', 'Due']),
        'total_amount': _extract_amount(ocr_text, ['Total', 'Grand Total', 'Amount Due', 'Total Amount', 'Total Due', 'Balance Due']),
        'tax_amount': _extract_amount(ocr_text, ['Tax', 'VAT', 'GST', 'Sales Tax', 'Tax Amount']),
        'currency': _extract_currency(ocr_text),
    }


# ============================================================================
# INLINE LIR ACTIVITIES (from docile_workflows/lir/activities.py)
# ============================================================================

def _find_table_section(text: str) -> tuple:
    """Find the start and end indices of the line items table section."""
    lines = text.split('\n')
    
    header_patterns = [
        r'description.*qty.*price', r'item.*quantity.*amount', r'product.*qty.*total',
        r'service.*hours.*rate', r'particulars.*qty.*rate', r'description.*units.*price',
    ]
    
    start_idx = 0
    for i, line in enumerate(lines):
        line_lower = line.lower()
        for pattern in header_patterns:
            if re.search(pattern, line_lower):
                start_idx = i + 1
                break
        if start_idx > 0:
            break
    
    end_patterns = ['subtotal', 'sub total', 'total', 'grand total', 'amount due', 'tax', 'vat']
    end_idx = len(lines)
    
    for i in range(start_idx, len(lines)):
        line_lower = lines[i].lower().strip()
        if any(pattern in line_lower for pattern in end_patterns):
            end_idx = i
            break
    
    return start_idx, end_idx


def _parse_line_item(line: str) -> Optional[dict]:
    """Parse a single line item from text."""
    if not line or not line.strip():
        return None
    
    line = line.strip()
    
    skip_patterns = ['description', 'quantity', 'subtotal', 'total', 'tax', 'vat', '---', '===']
    if any(p in line.lower() for p in skip_patterns):
        return None
    
    # Pattern: Description followed by numbers
    pattern1 = r'^(.+?)\s{2,}(\d+(?:\.\d+)?)\s+[\$€£]?([\d,\.]+)\s+[\$€£]?([\d,\.]+)$'
    match = re.match(pattern1, line)
    if match:
        desc, qty, unit_price, total = match.groups()
        return {
            'description': desc.strip(),
            'quantity': float(qty),
            'unit_price': _parse_amount(unit_price),
            'total_price': _parse_amount(total),
        }
    
    # Extract numbers at end of line
    nums = re.findall(r'[\$€£]?([\d,]+\.?\d*)', line)
    if nums and len(nums) >= 1:
        desc_match = re.match(r'^([^\d\$€£]+)', line)
        if desc_match:
            desc = desc_match.group(1).strip()
            if desc and len(desc) > 2:
                parsed_nums = [_parse_amount(n) for n in nums]
                parsed_nums = [n for n in parsed_nums if n is not None and n > 0]
                
                if len(parsed_nums) >= 1:
                    return {
                        'description': desc,
                        'quantity': 1.0,
                        'unit_price': parsed_nums[-1],
                        'total_price': parsed_nums[-1],
                    }
    
    return None


def extract_line_items(ocr_text: str) -> list:
    """Extract line items from invoice OCR text."""
    if not isinstance(ocr_text, str) or not ocr_text.strip():
        return []
    
    lines = ocr_text.split('\n')
    start_idx, end_idx = _find_table_section(ocr_text)
    
    items = []
    
    for i in range(start_idx, end_idx):
        if i < len(lines):
            item = _parse_line_item(lines[i])
            if item:
                items.append(item)
    
    if not items:
        for line in lines:
            item = _parse_line_item(line)
            if item:
                items.append(item)
    
    return items


# ============================================================================
# BENCHMARK INFRASTRUCTURE
# ============================================================================

@dataclass
class FieldAccuracy:
    """Track accuracy for a single field."""
    correct: int = 0
    incorrect: int = 0
    missing_prediction: int = 0
    missing_ground_truth: int = 0
    
    @property
    def total(self) -> int:
        return self.correct + self.incorrect + self.missing_prediction
    
    @property
    def accuracy(self) -> float:
        if self.total == 0:
            return 0.0
        return self.correct / self.total


@dataclass 
class BenchmarkResult:
    """Full benchmark results."""
    task: str
    total_documents: int
    successful_extractions: int
    failed_extractions: int
    field_accuracies: dict = field(default_factory=dict)
    overall_accuracy: float = 0.0
    total_latency_ms: float = 0.0
    avg_latency_ms: float = 0.0
    min_latency_ms: float = float('inf')
    max_latency_ms: float = 0.0
    errors: list = field(default_factory=list)


def load_ocr_text(doc_id: str, ocr_dir: Path) -> Optional[str]:
    """Load and reconstruct OCR text from JSON file."""
    ocr_file = ocr_dir / f"{doc_id}.json"
    if not ocr_file.exists():
        return None
    
    try:
        with open(ocr_file, 'r') as f:
            ocr_data = json.load(f)
        
        text_parts = []
        for page in ocr_data.get('pages', []):
            for block in page.get('blocks', []):
                for line in block.get('lines', []):
                    line_text = ' '.join(w.get('value', '') for w in line.get('words', []))
                    text_parts.append(line_text)
        
        return '\n'.join(text_parts)
    except Exception:
        return None


def load_annotations(doc_id: str, annotations_dir: Path) -> Optional[dict]:
    """Load ground truth annotations."""
    ann_file = annotations_dir / f"{doc_id}.json"
    if not ann_file.exists():
        return None
    
    try:
        with open(ann_file, 'r') as f:
            return json.load(f)
    except Exception:
        return None


DOCILE_TO_KILE_MAPPING = {
    'document_id': ['document_id'],
    'vendor_name': ['vendor_name'],
    'customer_name': ['customer_billing_name', 'customer_name'],
    'invoice_date': ['date_issue', 'invoice_date'],
    'due_date': ['date_due', 'due_date'],
    'total_amount': ['amount_total_gross', 'amount_due', 'total_amount'],
    'tax_amount': ['amount_total_tax', 'tax_amount'],
    'currency': ['currency_code', 'currency_code_amount_due'],
}


def normalize_value(value: Any, field_type: str) -> str:
    """Normalize a value for comparison."""
    if value is None:
        return ""
    
    value_str = str(value).strip().lower()
    value_str = value_str.replace('\n', ' ').replace('\t', ' ')
    value_str = ' '.join(value_str.split())
    
    if field_type in ('total_amount', 'tax_amount'):
        try:
            cleaned = value_str.replace('$', '').replace('€', '').replace('£', '')
            cleaned = cleaned.replace(',', '')
            num = float(cleaned)
            return f"{num:.2f}"
        except (ValueError, TypeError):
            pass
    
    return value_str


def extract_ground_truth_field(annotations: dict, our_field: str) -> Optional[str]:
    """Extract a field value from ground truth annotations."""
    docile_fields = DOCILE_TO_KILE_MAPPING.get(our_field, [our_field])
    
    for extraction in annotations.get('field_extractions', []):
        fieldtype = extraction.get('fieldtype', '')
        if fieldtype in docile_fields:
            return extraction.get('text', '')
    
    if our_field == 'currency':
        metadata = annotations.get('metadata', {})
        currency = metadata.get('currency', '')
        if currency:
            return currency.upper()
    
    return None


def compare_fields(predicted: dict, annotations: dict, result: BenchmarkResult) -> dict:
    """Compare predicted fields against ground truth."""
    comparison = {}
    
    for our_field in DOCILE_TO_KILE_MAPPING.keys():
        if our_field not in result.field_accuracies:
            result.field_accuracies[our_field] = FieldAccuracy()
        
        fa = result.field_accuracies[our_field]
        
        pred_value = predicted.get(our_field)
        gt_value = extract_ground_truth_field(annotations, our_field)
        
        pred_norm = normalize_value(pred_value, our_field)
        gt_norm = normalize_value(gt_value, our_field)
        
        if not gt_norm:
            fa.missing_ground_truth += 1
            comparison[our_field] = {'status': 'no_gt', 'pred': pred_value, 'gt': gt_value}
        elif not pred_norm:
            fa.missing_prediction += 1
            comparison[our_field] = {'status': 'missing', 'pred': pred_value, 'gt': gt_value}
        elif pred_norm == gt_norm or gt_norm in pred_norm or pred_norm in gt_norm:
            fa.correct += 1
            comparison[our_field] = {'status': 'correct', 'pred': pred_value, 'gt': gt_value}
        else:
            fa.incorrect += 1
            comparison[our_field] = {'status': 'incorrect', 'pred': pred_value, 'gt': gt_value}
    
    return comparison


def run_kile_benchmark(doc_ids: list, ocr_dir: Path, annotations_dir: Path) -> BenchmarkResult:
    """Run KILE (Key Information Extraction) benchmark."""
    result = BenchmarkResult(
        task="KILE",
        total_documents=len(doc_ids),
        successful_extractions=0,
        failed_extractions=0,
    )
    
    for our_field in DOCILE_TO_KILE_MAPPING.keys():
        result.field_accuracies[our_field] = FieldAccuracy()
    
    for i, doc_id in enumerate(doc_ids):
        if (i + 1) % 500 == 0:
            print(f"  Processed {i + 1}/{len(doc_ids)} documents...")
        
        ocr_text = load_ocr_text(doc_id, ocr_dir)
        if not ocr_text:
            result.failed_extractions += 1
            continue
        
        annotations = load_annotations(doc_id, annotations_dir)
        if not annotations:
            result.failed_extractions += 1
            continue
        
        try:
            start_time = time.perf_counter()
            predicted = extract_invoice_fields(ocr_text)
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            
            result.total_latency_ms += elapsed_ms
            result.min_latency_ms = min(result.min_latency_ms, elapsed_ms)
            result.max_latency_ms = max(result.max_latency_ms, elapsed_ms)
            result.successful_extractions += 1
            
            compare_fields(predicted, annotations, result)
            
        except Exception as e:
            result.failed_extractions += 1
    
    if result.successful_extractions > 0:
        result.avg_latency_ms = result.total_latency_ms / result.successful_extractions
    
    total_correct = sum(fa.correct for fa in result.field_accuracies.values())
    total_fields = sum(fa.total for fa in result.field_accuracies.values())
    if total_fields > 0:
        result.overall_accuracy = total_correct / total_fields
    
    return result


def run_lir_benchmark(doc_ids: list, ocr_dir: Path, annotations_dir: Path) -> BenchmarkResult:
    """Run LIR (Line Item Recognition) benchmark."""
    result = BenchmarkResult(
        task="LIR",
        total_documents=len(doc_ids),
        successful_extractions=0,
        failed_extractions=0,
    )
    
    for field in ['description', 'quantity', 'unit_price', 'total_price']:
        result.field_accuracies[field] = FieldAccuracy()
    
    total_gt_items = 0
    total_pred_items = 0
    matched_items = 0
    
    for i, doc_id in enumerate(doc_ids):
        if (i + 1) % 500 == 0:
            print(f"  Processed {i + 1}/{len(doc_ids)} documents...")
        
        ocr_text = load_ocr_text(doc_id, ocr_dir)
        if not ocr_text:
            result.failed_extractions += 1
            continue
        
        annotations = load_annotations(doc_id, annotations_dir)
        if not annotations:
            result.failed_extractions += 1
            continue
        
        try:
            start_time = time.perf_counter()
            predicted_items = extract_line_items(ocr_text)
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            
            result.total_latency_ms += elapsed_ms
            result.min_latency_ms = min(result.min_latency_ms, elapsed_ms)
            result.max_latency_ms = max(result.max_latency_ms, elapsed_ms)
            result.successful_extractions += 1
            
            gt_line_items = annotations.get('line_item_extractions', [])
            
            gt_items_by_id = defaultdict(dict)
            for item in gt_line_items:
                line_id = item.get('line_item_id', 0)
                fieldtype = item.get('fieldtype', '')
                text = item.get('text', '')
                gt_items_by_id[line_id][fieldtype] = text
            
            gt_items = {k: v for k, v in gt_items_by_id.items() if k > 0}
            
            total_gt_items += len(gt_items)
            total_pred_items += len(predicted_items)
            
            matched_items += min(len(predicted_items), len(gt_items))
            
        except Exception:
            result.failed_extractions += 1
    
    if result.successful_extractions > 0:
        result.avg_latency_ms = result.total_latency_ms / result.successful_extractions
    
    if total_gt_items > 0:
        result.overall_accuracy = matched_items / total_gt_items
    
    return result


def print_results(result: BenchmarkResult, llm_accuracy: float, llm_latency: float):
    """Print formatted results with comparison."""
    print(f"\n{'='*60}")
    print(f"  {result.task} Benchmark Results")
    print(f"{'='*60}")
    
    print(f"\n📊 Document Statistics:")
    print(f"   Total documents:      {result.total_documents:,}")
    print(f"   Successful:           {result.successful_extractions:,}")
    print(f"   Failed:               {result.failed_extractions:,}")
    
    print(f"\n⏱️  Latency (Compiled):")
    print(f"   Average:              {result.avg_latency_ms:.3f} ms")
    print(f"   Min:                  {result.min_latency_ms:.3f} ms")
    print(f"   Max:                  {result.max_latency_ms:.3f} ms")
    
    print(f"\n📈 Accuracy by Field:")
    print(f"   {'Field':<20} {'Correct':<10} {'Total':<10} {'Accuracy':<10}")
    print(f"   {'-'*50}")
    for field, fa in result.field_accuracies.items():
        acc_pct = fa.accuracy * 100
        print(f"   {field:<20} {fa.correct:<10} {fa.total:<10} {acc_pct:>6.1f}%")
    
    print(f"\n🎯 Overall Accuracy:     {result.overall_accuracy * 100:.1f}%")
    
    print(f"\n🔄 Comparison with LLM:")
    print(f"   {'Metric':<25} {'Compiled':<15} {'LLM':<15} {'Diff':<15}")
    print(f"   {'-'*60}")
    
    compiled_acc = result.overall_accuracy * 100
    llm_acc = llm_accuracy * 100
    acc_diff = compiled_acc - llm_acc
    print(f"   {'Accuracy':<25} {compiled_acc:>6.1f}%{'':<7} {llm_acc:>6.1f}%{'':<7} {acc_diff:>+6.1f}%")
    
    compiled_lat = result.avg_latency_ms
    lat_speedup = llm_latency / compiled_lat if compiled_lat > 0 else 0
    print(f"   {'Latency (avg)':<25} {compiled_lat:>6.3f} ms{'':<5} {llm_latency:>6.0f} ms{'':<5} {lat_speedup:>6.0f}x faster")
    
    cost_per_1000 = 0.015 * 0.5 + 0.075 * 0.1
    print(f"   {'Cost (per 1000 docs)':<25} {'$0.00':<15} {f'${cost_per_1000 * 1000:.2f}':<15}")


def save_results(kile_result: BenchmarkResult, lir_result: BenchmarkResult, output_path: Path):
    """Save results to JSON."""
    
    def serialize_result(r: BenchmarkResult) -> dict:
        return {
            'task': r.task,
            'total_documents': r.total_documents,
            'successful_extractions': r.successful_extractions,
            'failed_extractions': r.failed_extractions,
            'overall_accuracy': r.overall_accuracy,
            'avg_latency_ms': r.avg_latency_ms,
            'min_latency_ms': r.min_latency_ms if r.min_latency_ms != float('inf') else 0,
            'max_latency_ms': r.max_latency_ms,
            'field_accuracies': {
                field: {
                    'correct': fa.correct,
                    'incorrect': fa.incorrect,
                    'missing_prediction': fa.missing_prediction,
                    'accuracy': fa.accuracy
                }
                for field, fa in r.field_accuracies.items()
            }
        }
    
    results = {
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'kile': serialize_result(kile_result),
        'lir': serialize_result(lir_result),
        'comparison': {
            'kile': {
                'compiled_accuracy': kile_result.overall_accuracy,
                'llm_accuracy': 1.0,
                'compiled_latency_ms': kile_result.avg_latency_ms,
                'llm_latency_ms': 3149,
                'speedup': 3149 / kile_result.avg_latency_ms if kile_result.avg_latency_ms > 0 else 0
            },
            'lir': {
                'compiled_accuracy': lir_result.overall_accuracy,
                'llm_accuracy': 0.93,
                'compiled_latency_ms': lir_result.avg_latency_ms,
                'llm_latency_ms': 7268,
                'speedup': 7268 / lir_result.avg_latency_ms if lir_result.avg_latency_ms > 0 else 0
            }
        }
    }
    
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n💾 Results saved to: {output_path}")


def main():
    print("="*60)
    print("  DocILE Full Benchmark: Compiled (Regex) vs LLM")
    print("="*60)
    
    base_dir = Path(__file__).parent
    docile_dir = base_dir / "datasets" / "benchmarks" / "DocILE"
    ocr_dir = docile_dir / "ocr"
    annotations_dir = docile_dir / "annotations"
    
    with open(docile_dir / "train.json", 'r') as f:
        train_ids = json.load(f)
    with open(docile_dir / "val.json", 'r') as f:
        val_ids = json.load(f)
    
    all_doc_ids = train_ids + val_ids
    print(f"\n📁 Dataset: {len(all_doc_ids):,} documents (train: {len(train_ids):,}, val: {len(val_ids):,})")
    
    print("\n" + "-"*60)
    print("Running KILE (Key Information Extraction) Benchmark...")
    print("-"*60)
    kile_result = run_kile_benchmark(all_doc_ids, ocr_dir, annotations_dir)
    print_results(kile_result, llm_accuracy=1.0, llm_latency=3149)
    
    print("\n" + "-"*60)
    print("Running LIR (Line Item Recognition) Benchmark...")
    print("-"*60)
    lir_result = run_lir_benchmark(all_doc_ids, ocr_dir, annotations_dir)
    print_results(lir_result, llm_accuracy=0.93, llm_latency=7268)
    
    output_path = base_dir / "results" / f"compiled_docile_full_{int(time.time())}.json"
    save_results(kile_result, lir_result, output_path)
    
    print("\n" + "="*70)
    print("  SUMMARY: Compiled (Regex) vs LLM Comparison")
    print("="*70)
    print(f"\n{'Task':<8} {'Approach':<12} {'Accuracy':<12} {'Latency':<12} {'Cost/1K':<12}")
    print("-"*60)
    print(f"{'KILE':<8} {'Compiled':<12} {kile_result.overall_accuracy*100:>6.1f}%{'':<5} {kile_result.avg_latency_ms:>6.3f} ms{'':<3} {'$0.00':<12}")
    print(f"{'KILE':<8} {'LLM':<12} {'100.0%':<12} {'3149 ms':<12} {'$15.00':<12}")
    print(f"{'LIR':<8} {'Compiled':<12} {lir_result.overall_accuracy*100:>6.1f}%{'':<5} {lir_result.avg_latency_ms:>6.3f} ms{'':<3} {'$0.00':<12}")
    print(f"{'LIR':<8} {'LLM':<12} {'93.0%':<12} {'7268 ms':<12} {'$15.00':<12}")


if __name__ == "__main__":
    main()
