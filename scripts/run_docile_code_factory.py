#!/usr/bin/env python3
"""DocILE Code Factory benchmark with recovery logic.

Saves progress after each sample so it can resume if interrupted.
"""
import sys
import os
import json
import time
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
os.environ["TOKENIZERS_PARALLELISM"] = "false"

from compiled_ai.baselines.base import TaskInput
from compiled_ai.baselines.code_factory import CodeFactoryBaseline

# Config
RESULTS_FILE = Path("results/docile_code_factory_progress.json")
DOCILE_DIR = Path("datasets/benchmarks/DocILE")
MAX_SAMPLES = 100  # Set to None for full dataset

KILE_PROMPT = """Extract invoice fields from this noisy OCR-scanned document text.

IMPORTANT: This OCR text contains scanning artifacts, typos, and inconsistent formatting.
You MUST use LLM-based semantic understanding to extract fields accurately.
Regex/pattern matching will NOT work due to OCR noise.

Extract these fields as JSON:
- document_id: Invoice/receipt number
- vendor_name: Seller/vendor company name
- customer_name: Buyer/customer name  
- invoice_date: Invoice date (any format found)
- due_date: Payment due date (any format found)
- total_amount: Total amount as number
- tax_amount: Tax amount as number
- currency: Currency code (USD, EUR, etc.)

Return null for fields that cannot be confidently extracted.

OCR Text:
{ocr_text}

JSON:"""


def load_progress():
    """Load existing progress or create new."""
    if RESULTS_FILE.exists():
        data = json.loads(RESULTS_FILE.read_text())
        print(f"📂 Resuming from {len(data['completed'])} completed samples")
        return data
    return {
        "started": datetime.now().isoformat(),
        "completed": {},  # doc_id -> result
        "failed": {},     # doc_id -> error
        "stats": {"total_time": 0, "compile_time": 0}
    }


def save_progress(data):
    """Save progress to disk."""
    RESULTS_FILE.parent.mkdir(exist_ok=True)
    with open(RESULTS_FILE, "w") as f:
        json.dump(data, f, indent=2)


def load_ocr_text(doc_id):
    """Load OCR text for a document."""
    ocr_file = DOCILE_DIR / "ocr" / f"{doc_id}.json"
    if not ocr_file.exists():
        return None
    
    ocr_data = json.loads(ocr_file.read_text())
    text_parts = []
    for page in ocr_data.get("pages", []):
        for block in page.get("blocks", []):
            for line in block.get("lines", []):
                words = [w.get("value", "") for w in line.get("words", [])]
                text_parts.append(" ".join(words))
    return "\n".join(text_parts)


def main():
    print("=" * 60)
    print("DocILE Code Factory Benchmark (with recovery)")
    print("=" * 60)
    
    # Load document IDs
    val_ids = json.loads((DOCILE_DIR / "val.json").read_text())
    if MAX_SAMPLES:
        val_ids = val_ids[:MAX_SAMPLES]
    print(f"📊 Total documents: {len(val_ids)}")
    
    # Load progress
    progress = load_progress()
    completed_ids = set(progress["completed"].keys())
    remaining = [d for d in val_ids if d not in completed_ids]
    print(f"✅ Already completed: {len(completed_ids)}")
    print(f"⏳ Remaining: {len(remaining)}")
    
    if not remaining:
        print("\n🎉 All samples completed!")
        return
    
    # Initialize baseline (once)
    print("\n🏭 Initializing Code Factory...")
    baseline = CodeFactoryBaseline(
        provider="anthropic",
        verbose=True,  # Show compilation progress
        enable_security=False,
        enable_cache=True,  # IMPORTANT: Enable workflow caching for reuse
        cache_size=100,
        similarity_threshold=0.8,  # Require high similarity for reuse
    )
    print("✅ Baseline ready (caching enabled)\n")
    
    # Process remaining samples
    start_time = time.time()
    
    for i, doc_id in enumerate(remaining):
        print(f"\n[{len(completed_ids) + i + 1}/{len(val_ids)}] Processing {doc_id}...")
        
        # Load OCR
        ocr_text = load_ocr_text(doc_id)
        if not ocr_text:
            progress["failed"][doc_id] = "OCR file not found"
            save_progress(progress)
            continue
        
        # Create task
        task_input = TaskInput(
            task_id=f"docile_kile_{doc_id}",
            prompt=KILE_PROMPT.format(ocr_text=ocr_text[:3000]),
            context={},
            metadata={"output_format": "json"},
        )
        
        # Run extraction
        sample_start = time.time()
        try:
            result = baseline.run(task_input)
            latency = time.time() - sample_start
            
            progress["completed"][doc_id] = {
                "success": result.success,
                "latency_s": latency,
                "output": result.output,
                "error": result.error,
            }
            
            status = "✅" if result.success else "❌"
            print(f"  {status} Completed in {latency:.1f}s")
            if result.output:
                print(f"  📄 Output: {result.output[:100]}...")
                
        except Exception as e:
            progress["failed"][doc_id] = str(e)
            print(f"  ❌ Error: {e}")
        
        # Save progress after each sample
        progress["stats"]["total_time"] = time.time() - start_time
        save_progress(progress)
    
    # Final summary
    print("\n" + "=" * 60)
    print("FINAL RESULTS")
    print("=" * 60)
    
    completed = progress["completed"]
    successes = sum(1 for r in completed.values() if r.get("success"))
    total = len(completed)
    
    print(f"✅ Success: {successes}/{total} ({100*successes/total:.1f}%)")
    print(f"⏱️ Total time: {progress['stats']['total_time']:.1f}s")
    if completed:
        avg_latency = sum(r["latency_s"] for r in completed.values()) / len(completed)
        print(f"📊 Avg latency: {avg_latency:.1f}s")
    print(f"💾 Results saved to: {RESULTS_FILE}")


if __name__ == "__main__":
    main()
