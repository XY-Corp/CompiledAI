#!/usr/bin/env python3
"""Download BFCL v4 (Berkeley Function Calling Leaderboard) dataset.

Usage:
    python scripts/download_bfcl.py
    python scripts/download_bfcl.py --output datasets/bfcl_v4
"""

import argparse
from pathlib import Path


def download_bfcl(output_dir: Path) -> None:
    """Download BFCL v4 from HuggingFace.

    Args:
        output_dir: Directory to save the dataset
    """
    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        print("Error: huggingface-hub is required. Install with:")
        print("  pip install huggingface-hub")
        return

    output_dir.mkdir(parents=True, exist_ok=True)

    print("Downloading BFCL v4 from HuggingFace...")
    print("Repository: gorilla-llm/Berkeley-Function-Calling-Leaderboard")

    snapshot_download(
        repo_id="gorilla-llm/Berkeley-Function-Calling-Leaderboard",
        repo_type="dataset",
        local_dir=str(output_dir),
    )

    print(f"\nDownloaded BFCL v4 to {output_dir}")
    print("\nDataset structure:")
    print("  - simple*.jsonl: Simple function calls (400 AST, 100 executable)")
    print("  - multiple*.jsonl: Select from 2-4 functions (200 AST, 50 executable)")
    print("  - parallel*.jsonl: Multiple simultaneous calls (200 AST, 50 executable)")
    print("  - parallel_multiple*.jsonl: Complex scenarios (200 AST, 40 executable)")
    print("  - irrelevance*.jsonl: Irrelevant function detection")

    print("\nUsage example:")
    print('  from compiled_ai.runner import DatasetLoader')
    print('  loader = DatasetLoader("datasets")')
    print('  bfcl = loader.load_external("bfcl", "datasets/bfcl_v4")')


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Download BFCL v4 dataset from HuggingFace"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="datasets/bfcl_v4",
        help="Output directory (default: datasets/bfcl_v4)",
    )
    args = parser.parse_args()

    download_bfcl(Path(args.output))


if __name__ == "__main__":
    main()
