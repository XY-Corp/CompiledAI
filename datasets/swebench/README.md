# SWE-bench Dataset

Real-world GitHub issue resolution benchmark from Princeton NLP.

## Overview

SWE-bench evaluates language models on their ability to resolve real GitHub issues:
- **Input**: Issue description + codebase context
- **Output**: Unified diff patch that fixes the issue
- **Evaluation**: Tests pass/fail after applying patch

## Variants

| Variant | Tasks | Description |
|---------|-------|-------------|
| **Lite** | 300 | Curated subset, easier to run |
| **Verified** | 500 | Human-verified solvable |
| **Full** | 2,294 | Complete benchmark |

## Download

```bash
# Download SWE-bench Lite (recommended to start)
python scripts/download_swebench.py --variant lite

# Or download other variants
python scripts/download_swebench.py --variant verified
python scripts/download_swebench.py --variant full
```

## File Format

After download, you'll have:
```
datasets/swebench/
├── swebench_lite.json           # Main data file
├── swebench_lite_metadata.json  # Stats and metadata
└── README.md
```

## Task Structure

Each task contains:
```json
{
  "instance_id": "astropy__astropy-12907",
  "repo": "astropy/astropy",
  "base_commit": "d16bfe05a744909...",
  "problem_statement": "Issue description...",
  "hints_text": "Optional hints...",
  "patch": "diff --git a/...",
  "test_patch": "diff --git a/...",
  "FAIL_TO_PASS": "[\"test1\", \"test2\"]",
  "PASS_TO_PASS": "[\"test3\", \"test4\"]",
  "version": "4.3",
  "environment_setup_commit": "..."
}
```

## Running Evaluation

```bash
# Using the benchmark runner
python run_benchmark.py --dataset swebench --variant lite

# Or programmatically
from compiled_ai.datasets import SWEBenchConverter

converter = SWEBenchConverter()
instances = converter.load_file("datasets/swebench/swebench_lite.json")
```

## Docker Requirements

Full evaluation requires Docker to run tests in isolated environments:
```bash
pip install swebench
docker pull swebench/swebench
```

## References

- Paper: [SWE-bench: Can Language Models Resolve Real-World GitHub Issues?](https://arxiv.org/abs/2310.06770) (ICLR 2024 Oral)
- GitHub: https://github.com/princeton-nlp/SWE-bench
- HuggingFace: https://huggingface.co/datasets/princeton-nlp/SWE-bench_Lite
