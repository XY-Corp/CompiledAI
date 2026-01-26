#!/usr/bin/env python3
"""Download SWE-bench dataset from HuggingFace and save locally.

Usage:
    python scripts/download_swebench.py [--variant lite|verified|full]
"""

import argparse
import json
from pathlib import Path


def download_swebench(variant: str = "lite", output_dir: Path | None = None):
    """Download SWE-bench and save to local JSON file."""
    try:
        from datasets import load_dataset
    except ImportError:
        print("Installing datasets library...")
        import subprocess
        subprocess.run(["pip", "install", "datasets"], check=True)
        from datasets import load_dataset
    
    variants = {
        "lite": ("princeton-nlp/SWE-bench_Lite", 300),
        "verified": ("princeton-nlp/SWE-bench_Verified", 500),
        "full": ("princeton-nlp/SWE-bench", 2294),
    }
    
    if variant not in variants:
        raise ValueError(f"Unknown variant: {variant}")
    
    dataset_name, expected_count = variants[variant]
    
    print(f"Downloading {dataset_name}...")
    dataset = load_dataset(dataset_name, split="test")
    
    print(f"Loaded {len(dataset)} instances (expected ~{expected_count})")
    
    # Convert to list of dicts
    data = [dict(item) for item in dataset]
    
    # Set output directory
    if output_dir is None:
        output_dir = Path(__file__).parent.parent / "datasets" / "swebench"
    else:
        output_dir = Path(output_dir)
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Save main data file
    output_file = output_dir / f"swebench_{variant}.json"
    with open(output_file, "w") as f:
        json.dump(data, f, indent=2)
    
    print(f"Saved to {output_file}")
    
    # Generate metadata
    repos = {}
    for item in data:
        repo = item.get("repo", "unknown")
        repos[repo] = repos.get(repo, 0) + 1
    
    metadata = {
        "variant": variant,
        "dataset_name": dataset_name,
        "total_instances": len(data),
        "repos": repos,
        "fields": list(data[0].keys()) if data else [],
    }
    
    metadata_file = output_dir / f"swebench_{variant}_metadata.json"
    with open(metadata_file, "w") as f:
        json.dump(metadata, f, indent=2)
    
    print(f"Metadata saved to {metadata_file}")
    
    # Print summary
    print(f"\n{'='*50}")
    print(f"SWE-bench {variant} downloaded successfully!")
    print(f"{'='*50}")
    print(f"Total instances: {len(data)}")
    print(f"Repositories: {len(repos)}")
    print(f"\nTop 5 repos by task count:")
    for repo, count in sorted(repos.items(), key=lambda x: -x[1])[:5]:
        print(f"  {repo}: {count}")
    
    return output_file


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download SWE-bench dataset")
    parser.add_argument(
        "--variant", 
        choices=["lite", "verified", "full"],
        default="lite",
        help="Dataset variant (default: lite)"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Output directory (default: datasets/swebench)"
    )
    
    args = parser.parse_args()
    download_swebench(args.variant, args.output_dir)
