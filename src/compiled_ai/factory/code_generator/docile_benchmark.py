#!/usr/bin/env python3
"""DocILE benchmark runner using Crush generator.

Generates document extraction workflows and runs them on DocILE dataset.
"""

import json
import time
import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Literal

# Ensure ANTHROPIC_API_KEY is set
if not os.environ.get("ANTHROPIC_API_KEY"):
    env_file = Path(__file__).parent.parent.parent.parent.parent / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("ANTHROPIC_API_KEY="):
                key = line.split("=", 1)[1].strip().strip('"')
                os.environ["ANTHROPIC_API_KEY"] = key
                break

try:
    from .generator import CrushGenerator, GenerationResult
except ImportError:
    from generator import CrushGenerator, GenerationResult


TaskType = Literal["kile", "lir"]


@dataclass
class BenchmarkResult:
    """Result from running DocILE benchmark."""
    task_type: TaskType
    total_samples: int = 0
    successful_extractions: int = 0
    workflow_generation_time: float = 0.0
    total_extraction_time: float = 0.0
    errors: list[str] = field(default_factory=list)
    
    @property
    def success_rate(self) -> float:
        if self.total_samples == 0:
            return 0.0
        return self.successful_extractions / self.total_samples


# KILE task prompt - extract header fields from invoice
KILE_TASK = """
Create a workflow that extracts key information from invoice/receipt OCR text.

The workflow should:
1. Take raw OCR text as input
2. Extract these fields (return null if not found):
   - document_id: Invoice/receipt number
   - vendor_name: Name of the seller/vendor
   - vendor_address: Full address of vendor
   - customer_name: Name of buyer/customer
   - customer_address: Full address of customer
   - invoice_date: Date the invoice was issued
   - due_date: Payment due date
   - total_amount: Total amount to pay (numeric)
   - tax_amount: Tax amount if listed (numeric)
   - currency: Currency code (USD, EUR, etc.)
3. Return a dictionary with all fields

Use regex patterns and string matching. Be robust to OCR errors.
"""

# LIR task prompt - extract line items from invoice table
LIR_TASK = """
Create a workflow that extracts line items from invoice/receipt OCR text.

The workflow should:
1. Take raw OCR text as input
2. Find and parse the line items table
3. For each line item, extract:
   - description: Item description
   - quantity: Number of items (numeric)
   - unit_price: Price per unit (numeric)
   - total_price: Line total (numeric)
4. Return a list of dictionaries, one per line item

Handle various table formats. Be robust to OCR errors and missing fields.
"""


def load_docile_samples(
    docile_dir: Path,
    split: str = "val",
    max_samples: int = 10,
) -> list[dict]:
    """Load DocILE samples with OCR text and annotations."""
    
    # Load split IDs
    split_file = docile_dir / f"{split}.json"
    if not split_file.exists():
        raise FileNotFoundError(f"Split file not found: {split_file}")
    
    doc_ids = json.loads(split_file.read_text())[:max_samples]
    
    samples = []
    for doc_id in doc_ids:
        # Load OCR text (JSON format with pages/blocks/lines/words)
        ocr_file = docile_dir / "ocr" / f"{doc_id}.json"
        if not ocr_file.exists():
            continue
        
        # Extract text from OCR JSON
        try:
            ocr_data = json.loads(ocr_file.read_text())
            text_parts = []
            for page in ocr_data.get("pages", []):
                for block in page.get("blocks", []):
                    for line in block.get("lines", []):
                        words = [w.get("value", "") for w in line.get("words", [])]
                        text_parts.append(" ".join(words))
            ocr_text = "\n".join(text_parts)
        except Exception:
            continue
        
        # Load annotation
        ann_file = docile_dir / "annotations" / f"{doc_id}.json"
        if not ann_file.exists():
            continue
        
        annotation = json.loads(ann_file.read_text())
        
        samples.append({
            "id": doc_id,
            "ocr_text": ocr_text,
            "annotation": annotation,
        })
    
    return samples


def run_benchmark(
    task_type: TaskType = "kile",
    model: str = "anthropic/claude-opus-4-5-20251101",
    max_samples: int = 5,
    docile_dir: Path | None = None,
    output_dir: Path | None = None,
    verbose: bool = True,
) -> BenchmarkResult:
    """Run DocILE benchmark with Crush generator.
    
    Args:
        task_type: "kile" for key extraction, "lir" for line items
        model: Model to use for generation
        max_samples: Maximum samples to process
        docile_dir: Path to DocILE dataset
        output_dir: Where to save generated workflow
        verbose: Print progress
        
    Returns:
        BenchmarkResult with metrics
    """
    # Find DocILE directory
    if docile_dir is None:
        docile_dir = Path(__file__).parent.parent.parent.parent.parent / "datasets/benchmarks/DocILE"
    
    if output_dir is None:
        output_dir = Path(__file__).parent / "docile_workflows"
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    result = BenchmarkResult(task_type=task_type)
    
    if verbose:
        print(f"🔍 DocILE Benchmark: {task_type.upper()}")
        print(f"📁 Dataset: {docile_dir}")
        print(f"🤖 Model: {model}")
        print("=" * 50)
    
    # Step 1: Generate the extraction workflow
    if verbose:
        print("\n📋 Step 1: Generating extraction workflow...")
    
    generator = CrushGenerator(model=model, max_iterations=3)
    task_prompt = KILE_TASK if task_type == "kile" else LIR_TASK
    
    workflow_dir = output_dir / task_type
    gen_start = time.time()
    
    gen_result = generator.generate(
        task_prompt,
        output_dir=workflow_dir,
        verbose=verbose,
    )
    
    result.workflow_generation_time = time.time() - gen_start
    
    if not gen_result.success:
        result.errors.append(f"Workflow generation failed: {gen_result.errors}")
        if verbose:
            print(f"❌ Workflow generation failed!")
        return result
    
    if verbose:
        print(f"✅ Workflow generated in {result.workflow_generation_time:.1f}s")
    
    # Step 2: Load samples
    if verbose:
        print(f"\n📂 Step 2: Loading {max_samples} samples...")
    
    try:
        samples = load_docile_samples(docile_dir, max_samples=max_samples)
        result.total_samples = len(samples)
        if verbose:
            print(f"   Loaded {len(samples)} samples")
    except Exception as e:
        result.errors.append(f"Failed to load samples: {e}")
        if verbose:
            print(f"❌ Failed to load samples: {e}")
        return result
    
    # Step 3: Run extraction on each sample
    if verbose:
        print(f"\n🔄 Step 3: Running extractions...")
    
    # Load the generated activities module
    activities_path = workflow_dir / "activities.py"
    if not activities_path.exists():
        result.errors.append("activities.py not found")
        return result
    
    # Import the generated module
    import importlib.util
    spec = importlib.util.spec_from_file_location("activities", activities_path)
    activities_module = importlib.util.module_from_spec(spec)
    
    try:
        spec.loader.exec_module(activities_module)
    except Exception as e:
        result.errors.append(f"Failed to load activities: {e}")
        if verbose:
            print(f"❌ Failed to load activities: {e}")
        return result
    
    # Find the main extraction function (non-private, has 'extract' in name)
    extract_fn = None
    for name in dir(activities_module):
        if not name.startswith("_") and "extract" in name.lower() and callable(getattr(activities_module, name)):
            extract_fn = getattr(activities_module, name)
            break
    
    # Fallback: look for any function that takes a single string argument
    if extract_fn is None:
        for name in dir(activities_module):
            if name.startswith("_"):
                continue
            fn = getattr(activities_module, name)
            if callable(fn) and hasattr(fn, "__code__") and fn.__code__.co_argcount == 1:
                extract_fn = fn
                break
    
    if extract_fn is None:
        result.errors.append("No extraction function found in activities.py")
        return result
    
    if verbose:
        print(f"   Using function: {extract_fn.__name__}")
    
    extraction_start = time.time()
    
    for i, sample in enumerate(samples):
        try:
            output = extract_fn(sample["ocr_text"])
            
            # Basic validation - check if we got something
            if output and (isinstance(output, dict) or isinstance(output, list)):
                result.successful_extractions += 1
                if verbose:
                    print(f"   ✅ [{i+1}/{len(samples)}] {sample['id']}")
            else:
                if verbose:
                    print(f"   ⚠️ [{i+1}/{len(samples)}] {sample['id']} - empty output")
                    
        except Exception as e:
            result.errors.append(f"{sample['id']}: {str(e)[:100]}")
            if verbose:
                print(f"   ❌ [{i+1}/{len(samples)}] {sample['id']} - {str(e)[:50]}")
    
    result.total_extraction_time = time.time() - extraction_start
    
    # Summary
    if verbose:
        print("\n" + "=" * 50)
        print("📊 RESULTS")
        print(f"   Task: {task_type.upper()}")
        print(f"   Samples: {result.total_samples}")
        print(f"   Successful: {result.successful_extractions}")
        print(f"   Success Rate: {result.success_rate:.1%}")
        print(f"   Workflow Gen Time: {result.workflow_generation_time:.1f}s")
        print(f"   Total Extraction Time: {result.total_extraction_time:.1f}s")
        if result.errors:
            print(f"   Errors: {len(result.errors)}")
    
    return result


def main():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Run DocILE benchmark with Crush generator")
    parser.add_argument("--task", choices=["kile", "lir"], default="kile",
                        help="Task type: kile (key info) or lir (line items)")
    parser.add_argument("--model", default="anthropic/claude-opus-4-5-20251101",
                        help="Model to use")
    parser.add_argument("--samples", type=int, default=5,
                        help="Number of samples to process")
    parser.add_argument("--docile-dir", type=Path,
                        help="Path to DocILE dataset")
    parser.add_argument("-q", "--quiet", action="store_true",
                        help="Quiet mode")
    
    args = parser.parse_args()
    
    result = run_benchmark(
        task_type=args.task,
        model=args.model,
        max_samples=args.samples,
        docile_dir=args.docile_dir,
        verbose=not args.quiet,
    )
    
    # Exit with error if no successes
    if result.successful_extractions == 0:
        exit(1)


if __name__ == "__main__":
    main()
