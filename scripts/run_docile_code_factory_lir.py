#!/usr/bin/env python3
"""DocILE Code Factory benchmark - LIR task with recovery."""
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

RESULTS_FILE = Path("results/docile_code_factory_lir_progress.json")
DOCILE_DIR = Path("datasets/benchmarks/DocILE")
MAX_SAMPLES = 100

LIR_PROMPT = """Extract line items from this noisy OCR-scanned invoice document.

IMPORTANT: This OCR text contains scanning artifacts, typos, and inconsistent formatting.
You MUST use LLM-based semantic understanding to extract line items accurately.
Regex/pattern matching will NOT work due to OCR noise.

Extract line items as a JSON array. Each line item should have:
- description: Item/service description
- quantity: Number of units (number or null)
- unit_price: Price per unit (number or null)  
- total_price: Line total (number or null)

Return empty array [] if no line items can be confidently extracted.

OCR Text:
{ocr_text}

JSON:"""


def load_progress():
    if RESULTS_FILE.exists():
        data = json.loads(RESULTS_FILE.read_text())
        print(f"📂 Resuming from {len(data['completed'])} completed samples")
        return data
    return {"started": datetime.now().isoformat(), "completed": {}, "failed": {}, "stats": {"total_time": 0}}


def save_progress(data):
    RESULTS_FILE.parent.mkdir(exist_ok=True)
    with open(RESULTS_FILE, "w") as f:
        json.dump(data, f, indent=2)


def load_ocr_text(doc_id):
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
    print("DocILE Code Factory Benchmark - LIR (with recovery)")
    print("=" * 60)
    
    val_ids = json.loads((DOCILE_DIR / "val.json").read_text())
    if MAX_SAMPLES:
        val_ids = val_ids[:MAX_SAMPLES]
    print(f"📊 Total documents: {len(val_ids)}")
    
    progress = load_progress()
    completed_ids = set(progress["completed"].keys())
    remaining = [d for d in val_ids if d not in completed_ids]
    print(f"✅ Already completed: {len(completed_ids)}")
    print(f"⏳ Remaining: {len(remaining)}")
    
    if not remaining:
        print("\n🎉 All samples completed!")
        return
    
    print("\n🏭 Initializing Code Factory...")
    baseline = CodeFactoryBaseline(
        provider="anthropic", 
        verbose=True, 
        enable_security=False,
        enable_cache=True,  # IMPORTANT: Enable workflow caching
        cache_size=100,
        similarity_threshold=0.8,
    )
    print("✅ Baseline ready (caching enabled)\n")
    
    start_time = time.time()
    
    for i, doc_id in enumerate(remaining):
        print(f"\n[{len(completed_ids) + i + 1}/{len(val_ids)}] Processing {doc_id}...")
        
        ocr_text = load_ocr_text(doc_id)
        if not ocr_text:
            progress["failed"][doc_id] = "OCR file not found"
            save_progress(progress)
            continue
        
        task_input = TaskInput(
            task_id=f"docile_lir_{doc_id}",
            prompt=LIR_PROMPT.format(ocr_text=ocr_text[:3000]),
            context={},
            metadata={"output_format": "json"},
        )
        
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
                
        except Exception as e:
            progress["failed"][doc_id] = str(e)
            print(f"  ❌ Error: {e}")
        
        progress["stats"]["total_time"] = time.time() - start_time
        save_progress(progress)
    
    print("\n" + "=" * 60)
    completed = progress["completed"]
    successes = sum(1 for r in completed.values() if r.get("success"))
    print(f"✅ Success: {successes}/{len(completed)} ({100*successes/len(completed):.1f}%)")
    print(f"💾 Results: {RESULTS_FILE}")


if __name__ == "__main__":
    main()
