"""BFCL converter - converts BFCL format to generic DatasetInstance.

Auto-generates output_format from function definitions for LLM evaluation.
"""

import json
from itertools import product
from pathlib import Path
from typing import Any

from .base import DatasetConverter, DatasetInstance


class BFCLConverter(DatasetConverter):
    """Converts BFCL format to generic DatasetInstance.

    BFCL has TWO files:
    1. Input file: {"id": "simple_0", "question": [[{"role": "user", "content": "..."}]], "function": [...]}
    2. Answer file: {"id": "simple_0", "ground_truth": [{"func_name": {"param": [valid_values]}}]}

    The ground_truth uses ARRAYS for multiple valid values:
    {"calculate_area": {"base": [10], "height": [5], "unit": ["units", ""]}}

    This means:
    - base must be 10
    - height must be 5
    - unit can be "units" OR omitted (empty string means optional)

    We EXPAND this into all valid combinations at conversion time:
    possible_outputs = [
        {"calculate_area": {"base": 10, "height": 5, "unit": "units"}},
        {"calculate_area": {"base": 10, "height": 5}}  # unit omitted
    ]
    """

    def convert(self, raw_data: dict) -> list[DatasetInstance]:
        """Convert raw BFCL data to DatasetInstance list.

        Args:
            raw_data: Dict with 'inputs' and 'answers' keys containing the joined data

        Structure:
        - input: The COMPLETE raw input (question + functions as JSON)
        - output_format: Auto-generated from function definitions (structure only)
        - expected_output: First valid output for LLM evaluation
        - context: Functions schema hash for signature grouping only
        - possible_outputs: All valid answers (deprecated, kept for compatibility)
        """
        instances = []

        for item in raw_data.get("items", []):
            inst_id = item.get("id", "unknown")

            # Get raw components
            question = item.get("question", "")
            functions = item.get("function", [])

            # The input is the COMPLETE raw data - no parsing
            # This is exactly what the workflow will receive
            raw_input = json.dumps({
                "question": question,
                "function": functions,
            })

            # Generate output_format from function definitions
            output_format = self._generate_output_format(functions)

            # Expand ground truth into all possible outputs
            ground_truth = item.get("ground_truth", [])
            possible_outputs = self._expand_ground_truth(ground_truth)

            # First valid output is used for LLM evaluation
            expected_output = possible_outputs[0] if possible_outputs else None

            instances.append(DatasetInstance(
                id=inst_id,
                input=raw_input,  # Complete raw input as JSON
                output_format=output_format,  # Auto-generated from functions
                expected_output=expected_output,  # For LLM evaluation
                context={
                    "functions": functions,  # For signature grouping only
                },
                possible_outputs=possible_outputs,  # Deprecated, kept for compatibility
            ))

        return instances

    def _generate_output_format(self, functions: list[dict]) -> dict:
        """Generate output_format from function definitions.

        The output format describes the structure WITHOUT specific values.
        For BFCL, output is a function call: {func_name: {param: value, ...}}

        IMPORTANT: Function names are TOP-LEVEL keys, not nested under "functions".

        Example input (function definition):
        {
            "name": "calculate_area",
            "parameters": {
                "properties": {
                    "base": {"type": "number", "description": "Base length"},
                    "height": {"type": "number", "description": "Height"}
                }
            }
        }

        Example output (output_format):
        {
            "type": "object",
            "description": "A single function call with the function name as the top-level key and its parameters as a nested object",
            "calculate_area": {
                "base": "number - Base length",
                "height": "number - Height"
            }
        }
        """
        if not functions:
            return {"type": "object", "description": "A single function call with the function name as the top-level key and its parameters as a nested object"}

        output_format = {
            "type": "object",
            "description": "A single function call with the function name as the top-level key and its parameters as a nested object"
        }

        for func in functions:
            func_name = func.get("name", "unknown")
            params_schema = func.get("parameters", {})
            properties = params_schema.get("properties", {})

            func_params = {}
            for param_name, param_def in properties.items():
                param_type = param_def.get("type", "any")
                param_desc = param_def.get("description", param_name)
                func_params[param_name] = f"{param_type} - {param_desc}"

            # Add function name as TOP-LEVEL key (not under "functions")
            output_format[func_name] = func_params

        return output_format

    def _expand_ground_truth(self, ground_truth: list[dict]) -> list[dict]:
        """Expand BFCL ground truth arrays into all valid output combinations.

        Input: [{"func": {"param1": [val1], "param2": [val2a, val2b]}}]
        Output: [
            {"func": {"param1": val1, "param2": val2a}},
            {"func": {"param1": val1, "param2": val2b}}
        ]
        """
        all_outputs = []

        for func_call in ground_truth:
            for func_name, params in func_call.items():
                if not isinstance(params, dict):
                    # Not a function call format, keep as-is
                    all_outputs.append(func_call)
                    continue

                # Expand parameter combinations
                expanded = self._expand_params(func_name, params)
                all_outputs.extend(expanded)

        return all_outputs

    def _expand_params(self, func_name: str, params: dict) -> list[dict]:
        """Expand parameter arrays into all combinations."""
        # Separate required params (no empty string option) from optional
        param_options = {}
        for param_name, values in params.items():
            if isinstance(values, list):
                param_options[param_name] = values
            else:
                param_options[param_name] = [values]

        # Generate all combinations
        param_names = list(param_options.keys())
        if not param_names:
            return [{func_name: {}}]

        value_lists = [param_options[name] for name in param_names]
        combinations = list(product(*value_lists))

        results = []
        for combo in combinations:
            result_params = {}
            for name, value in zip(param_names, combo):
                # Empty string means "omit this parameter"
                if value != "":
                    result_params[name] = value
            results.append({func_name: result_params})

        return results

    def load_file(self, input_path: str, answer_path: str | None = None) -> list[DatasetInstance]:
        """Load BFCL dataset from input and answer files.

        Args:
            input_path: Path to input JSON/JSONL file
            answer_path: Path to answer JSON/JSONL file (if None, looks in possible_answer/)
        """
        input_path = Path(input_path)

        # Auto-detect answer file location
        if answer_path is None:
            answer_dir = input_path.parent / "possible_answer"
            answer_path = answer_dir / input_path.name

        # Load input file (JSONL format - one JSON per line)
        inputs = []
        with open(input_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    inputs.append(json.loads(line))

        # Load answer file (also JSONL)
        answers = {}
        if Path(answer_path).exists():
            with open(answer_path) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        item = json.loads(line)
                        answers[item.get("id")] = item.get("ground_truth", [])

        # Join inputs with answers
        items = []
        for inp in inputs:
            item_id = inp.get("id")
            items.append({
                "id": item_id,
                "question": inp.get("question", ""),
                "function": inp.get("function", []),
                "ground_truth": answers.get(item_id, []),
            })

        return self.convert({"items": items})

    def load_directory(self, dir_path: str) -> list[DatasetInstance]:
        """Load all BFCL files from a directory."""
        instances = []
        path = Path(dir_path)

        for json_file in path.glob("*.json"):
            # Skip answer directory files
            if "possible_answer" in str(json_file):
                continue
            instances.extend(self.load_file(str(json_file)))

        return instances
