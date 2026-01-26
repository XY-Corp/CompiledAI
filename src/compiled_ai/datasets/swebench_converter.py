"""SWE-bench converter - converts SWE-bench format to generic DatasetInstance.

SWE-bench: Real-world GitHub issue resolution benchmark.
Agent receives issue + codebase, must generate a patch that fixes the issue.

Strategy:
- `input`: Problem statement (GitHub issue text)
- `output_format`: Expected output structure (unified diff patch)
- `expected_output`: Ground truth patch + test info for evaluation
- `context`: Repo info, base commit, test requirements for signature grouping
"""

import json
from pathlib import Path
from typing import Any

from .base import DatasetConverter, DatasetInstance


class SWEBenchConverter(DatasetConverter):
    """Converts SWE-bench format to generic DatasetInstance.
    
    SWE-bench format (from HuggingFace):
    {
        "repo": "astropy/astropy",
        "instance_id": "astropy__astropy-12907",
        "base_commit": "d16bfe05a744909...",
        "patch": "diff --git a/... ",
        "test_patch": "diff --git a/...",
        "problem_statement": "Issue description...",
        "hints_text": "",
        "FAIL_TO_PASS": "[\"test1\", \"test2\"]",
        "PASS_TO_PASS": "[\"test3\", \"test4\"]",
        ...
    }
    
    Converts to:
    DatasetInstance(
        id="astropy__astropy-12907",
        input="Issue description...",
        output_format={"type": "unified_diff", "description": "..."},
        expected_output={"patch": "...", "tests": {...}},
        context={"repo": "...", "base_commit": "...", ...}
    )
    """
    
    # Standard output format for all SWE-bench tasks
    OUTPUT_FORMAT = {
        "type": "unified_diff",
        "description": "A unified diff patch that resolves the GitHub issue",
        "format": "diff --git a/path/to/file ...",
        "requirements": [
            "Must be valid unified diff format",
            "Must apply cleanly to the base_commit",
            "Must make FAIL_TO_PASS tests pass",
            "Must not break PASS_TO_PASS tests"
        ]
    }
    
    def convert(self, raw_data: dict) -> list[DatasetInstance]:
        """Convert raw SWE-bench task data to DatasetInstance list.
        
        Args:
            raw_data: Single SWE-bench instance
            
        Returns:
            List containing one DatasetInstance
        """
        instance_id = raw_data.get("instance_id", raw_data.get("id", "unknown"))
        
        # Parse test lists (stored as JSON strings in the dataset)
        fail_to_pass = self._parse_test_list(raw_data.get("FAIL_TO_PASS", "[]"))
        pass_to_pass = self._parse_test_list(raw_data.get("PASS_TO_PASS", "[]"))
        
        # Build the input - this is what the agent sees
        problem_statement = raw_data.get("problem_statement", "")
        hints = raw_data.get("hints_text", "")
        
        # Include hints if available
        if hints and hints.strip():
            input_text = f"{problem_statement}\n\n---\nHints:\n{hints}"
        else:
            input_text = problem_statement
        
        # Expected output for evaluation
        expected_output = {
            "patch": raw_data.get("patch", ""),
            "test_patch": raw_data.get("test_patch", ""),
            "fail_to_pass": fail_to_pass,
            "pass_to_pass": pass_to_pass,
        }
        
        # Context for signature grouping and execution
        # Tasks from same repo/version can share workflow patterns
        context = {
            "repo": raw_data.get("repo", ""),
            "base_commit": raw_data.get("base_commit", ""),
            "version": raw_data.get("version", ""),
            "environment_setup_commit": raw_data.get("environment_setup_commit", ""),
            "created_at": raw_data.get("created_at", ""),
            # Workflow metadata
            "_task_type": "code_patch",
            "_eval_type": "swebench",
        }
        
        return [DatasetInstance(
            id=instance_id,
            input=input_text,
            output_format=self.OUTPUT_FORMAT,
            expected_output=expected_output,
            context=context,
            possible_outputs=[raw_data.get("patch", "")],  # For legacy compatibility
        )]
    
    def load_file(self, path: str) -> list[DatasetInstance]:
        """Load SWE-bench dataset from file.
        
        Supports:
        - JSON file with list of instances
        - JSONL file with one instance per line
        - Parquet file (requires pyarrow)
        
        Args:
            path: Path to dataset file
            
        Returns:
            List of DatasetInstance
        """
        path = Path(path)
        instances = []
        
        if path.suffix == ".json":
            with open(path) as f:
                data = json.load(f)
            if isinstance(data, list):
                for item in data:
                    instances.extend(self.convert(item))
            else:
                instances.extend(self.convert(data))
                
        elif path.suffix == ".jsonl":
            with open(path) as f:
                for line in f:
                    if line.strip():
                        item = json.loads(line)
                        instances.extend(self.convert(item))
                        
        elif path.suffix == ".parquet":
            try:
                import pyarrow.parquet as pq
                table = pq.read_table(path)
                for i in range(len(table)):
                    row = {col: table[col][i].as_py() for col in table.column_names}
                    instances.extend(self.convert(row))
            except ImportError:
                raise ImportError("pyarrow required for parquet files: pip install pyarrow")
        else:
            raise ValueError(f"Unsupported file format: {path.suffix}")
        
        return instances
    
    def load_from_huggingface(
        self, 
        dataset_name: str = "princeton-nlp/SWE-bench_Lite",
        split: str = "test",
        max_instances: int | None = None
    ) -> list[DatasetInstance]:
        """Load SWE-bench directly from HuggingFace.
        
        Args:
            dataset_name: HuggingFace dataset identifier
            split: Dataset split (test, dev, train)
            max_instances: Maximum number of instances to load
            
        Returns:
            List of DatasetInstance
        """
        try:
            from datasets import load_dataset
        except ImportError:
            raise ImportError("datasets required: pip install datasets")
        
        dataset = load_dataset(dataset_name, split=split)
        
        instances = []
        for i, item in enumerate(dataset):
            if max_instances and i >= max_instances:
                break
            instances.extend(self.convert(dict(item)))
        
        return instances
    
    def _parse_test_list(self, test_str: str) -> list[str]:
        """Parse test list from JSON string."""
        if not test_str:
            return []
        try:
            return json.loads(test_str)
        except json.JSONDecodeError:
            return []


# Convenience function for quick loading
def load_swebench(
    variant: str = "lite",
    split: str = "test", 
    max_instances: int | None = None
) -> list[DatasetInstance]:
    """Load SWE-bench dataset.
    
    Args:
        variant: "lite" (300), "verified" (500), or "full" (2294)
        split: Dataset split
        max_instances: Max instances to load
        
    Returns:
        List of DatasetInstance
    """
    variants = {
        "lite": "princeton-nlp/SWE-bench_Lite",
        "verified": "princeton-nlp/SWE-bench_Verified", 
        "full": "princeton-nlp/SWE-bench",
    }
    
    if variant not in variants:
        raise ValueError(f"Unknown variant: {variant}. Choose from {list(variants.keys())}")
    
    converter = SWEBenchConverter()
    return converter.load_from_huggingface(
        dataset_name=variants[variant],
        split=split,
        max_instances=max_instances
    )
