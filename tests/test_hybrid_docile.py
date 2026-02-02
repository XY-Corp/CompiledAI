#!/usr/bin/env python3
"""Benchmark test for hybrid DocILE extraction.

Compares hybrid approach against:
- Pure regex: 35.7% accuracy, 1.1ms/sample
- Pure LLM: 100% accuracy, 3149ms/sample

Target: >80% accuracy with <500ms average latency
"""

import json
import sys
import time
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from compiled_ai.datasets.docile_converter import DocILEConverter
from compiled_ai.factory.code_generator.docile_workflows.kile.hybrid_extractor import (
    HybridExtractor,
    normalize_for_comparison,
)


def run_benchmark():
    """Run the hybrid DocILE benchmark."""
    
    print("\n" + "="*70)
    print("  HYBRID DocILE EXTRACTION BENCHMARK")
    print("="*70)
    
    # Configuration
    dataset_path = Path(__file__).parent.parent / "datasets" / "benchmarks" / "DocILE"
    num_samples = 15
    
    print(f"\nDataset: {dataset_path}")
    print(f"Samples: {num_samples}")
    
    # Load dataset
    print("\n📁 Loading DocILE samples...")
    converter = DocILEConverter()
    instances = converter.load_directory(str(dataset_path), task_type="kile")[:num_samples]
    print(f"   Loaded {len(instances)} samples")
    
    # Initialize extractor
    extractor = HybridExtractor(
        model="claude-sonnet-4-20250514",  # Fast, good quality
        confidence_threshold=0.5,
    )
    
    print(f"\n⚙️  Configuration:")
    print(f"   Model: {extractor.model}")
    print(f"   Confidence threshold: {extractor.confidence_threshold}")
    
    # Run benchmark
    print("\n🚀 Running hybrid extraction...")
    print("-"*70)
    
    results = {
        "timestamp": datetime.now().strftime("%Y%m%d_%H%M%S"),
        "num_samples": len(instances),
        "config": {
            "confidence_threshold": extractor.confidence_threshold,
            "model": extractor.model,
        },
        "samples": [],
        "field_results": {field: {"correct": 0, "total": 0} for field in HybridExtractor.KILE_FIELDS},
    }
    
    total_correct = 0
    total_fields = 0
    samples_with_llm = 0
    total_regex_time = 0.0
    total_llm_time = 0.0
    total_input_tokens = 0
    total_output_tokens = 0
    
    for i, instance in enumerate(instances):
        # Parse input
        input_data = json.loads(instance.input)
        ocr_text = input_data["document_text"]
        expected = instance.expected_output
        
        # Run extraction
        start = time.perf_counter()
        result = extractor.extract(ocr_text)
        elapsed = (time.perf_counter() - start) * 1000
        
        # Calculate accuracy
        correct = 0
        field_count = 0
        field_details = {}
        
        for field in HybridExtractor.KILE_FIELDS:
            if field in expected:
                field_count += 1
                results["field_results"][field]["total"] += 1
                
                extracted = result.fields.get(field)
                exp_val = expected.get(field)
                is_match = normalize_for_comparison(extracted, exp_val)
                
                if is_match:
                    correct += 1
                    results["field_results"][field]["correct"] += 1
                
                field_details[field] = {
                    "extracted": extracted,
                    "expected": exp_val,
                    "match": is_match,
                    "confidence": result.confidence.get(field, 0),
                }
        
        accuracy = correct / field_count if field_count > 0 else 0
        
        # Track stats
        total_correct += correct
        total_fields += field_count
        if result.used_llm:
            samples_with_llm += 1
        total_regex_time += result.regex_time_ms
        total_llm_time += result.llm_time_ms
        total_input_tokens += result.input_tokens
        total_output_tokens += result.output_tokens
        
        # Print progress
        llm_indicator = "🤖" if result.used_llm else "📐"
        status = "✓" if accuracy >= 0.8 else "⚠️" if accuracy >= 0.5 else "✗"
        print(f"   [{i+1:2d}/{num_samples}] {status} {llm_indicator} {instance.id[:24]:24s} "
              f"| acc={accuracy:.0%} ({correct}/{field_count}) | {elapsed:.0f}ms")
        
        if result.used_llm:
            print(f"           LLM fields: {result.llm_fields}")
        
        results["samples"].append({
            "id": instance.id,
            "accuracy": accuracy,
            "correct": correct,
            "total": field_count,
            "used_llm": result.used_llm,
            "llm_fields": result.llm_fields,
            "regex_time_ms": result.regex_time_ms,
            "llm_time_ms": result.llm_time_ms,
            "total_time_ms": result.total_time_ms,
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
            "field_details": field_details,
        })
    
    # Calculate summary
    overall_accuracy = total_correct / total_fields if total_fields > 0 else 0
    avg_time = (total_regex_time + total_llm_time) / num_samples
    llm_rate = samples_with_llm / num_samples
    total_tokens = total_input_tokens + total_output_tokens
    
    print("-"*70)
    print("\n📊 RESULTS SUMMARY")
    print("-"*70)
    print(f"   Overall field accuracy: {overall_accuracy:.1%} ({total_correct}/{total_fields})")
    print(f"   Samples using LLM:      {samples_with_llm}/{num_samples} ({llm_rate:.0%})")
    print(f"   Average latency:        {avg_time:.1f}ms")
    print(f"   Total tokens used:      {total_tokens:,}")
    print(f"   Avg tokens/sample:      {total_tokens/num_samples:.0f}")
    
    print("\n📈 FIELD-LEVEL ACCURACY")
    print("-"*70)
    for field, stats in results["field_results"].items():
        if stats["total"] > 0:
            acc = stats["correct"] / stats["total"]
            bar = "█" * int(acc * 20) + "░" * (20 - int(acc * 20))
            print(f"   {field:20s} {bar} {acc:.0%} ({stats['correct']}/{stats['total']})")
    
    print("\n🆚 COMPARISON VS BASELINES")
    print("-"*70)
    print(f"   {'Approach':<20s} {'Accuracy':>12s} {'Latency':>12s} {'Tokens':>12s}")
    print(f"   {'-'*20} {'-'*12} {'-'*12} {'-'*12}")
    print(f"   {'Pure Regex':<20s} {'35.7%':>12s} {'1.1ms':>12s} {'0':>12s}")
    print(f"   {'Pure LLM':<20s} {'100%':>12s} {'3149ms':>12s} {'~1000':>12s}")
    print(f"   {'HYBRID':<20s} {f'{overall_accuracy:.1%}':>12s} {f'{avg_time:.0f}ms':>12s} {f'{total_tokens/num_samples:.0f}':>12s}")
    
    # Check targets
    print("\n🎯 TARGET ASSESSMENT")
    print("-"*70)
    accuracy_target = overall_accuracy >= 0.80
    latency_target = avg_time < 500
    
    print(f"   Accuracy ≥80%:   {'✅ PASS' if accuracy_target else '❌ FAIL'} ({overall_accuracy:.1%})")
    print(f"   Latency <500ms:  {'✅ PASS' if latency_target else '❌ FAIL'} ({avg_time:.0f}ms)")
    
    if accuracy_target and latency_target:
        print("\n   🎉 ALL TARGETS MET!")
    else:
        print("\n   ⚠️  Some targets not met")
    
    # Save results
    results["summary"] = {
        "overall_accuracy": overall_accuracy,
        "total_correct": total_correct,
        "total_fields": total_fields,
        "samples_with_llm": samples_with_llm,
        "llm_usage_rate": llm_rate,
        "avg_latency_ms": avg_time,
        "total_tokens": total_tokens,
        "avg_tokens_per_sample": total_tokens / num_samples,
        "targets": {
            "accuracy_met": accuracy_target,
            "latency_met": latency_target,
        },
    }
    
    # Save to results directory
    output_path = Path(__file__).parent.parent / "results" / f"docile_hybrid_benchmark_{results['timestamp']}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\n💾 Results saved to: {output_path.name}")
    print("="*70)
    
    return results


if __name__ == "__main__":
    run_benchmark()
