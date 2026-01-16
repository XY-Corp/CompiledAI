"""Concrete evaluator implementations."""

import json
import re
from difflib import SequenceMatcher
from typing import Any

from .base import EvaluationResult, Evaluator, register_evaluator


@register_evaluator("exact_match")
class ExactMatchEvaluator(Evaluator):
    """Exact string match evaluator."""

    def __init__(self, case_sensitive: bool = True, strip_whitespace: bool = True):
        """Initialize exact match evaluator.

        Args:
            case_sensitive: Whether comparison is case-sensitive
            strip_whitespace: Whether to strip leading/trailing whitespace
        """
        self.case_sensitive = case_sensitive
        self.strip_whitespace = strip_whitespace

    def evaluate(self, output: str, expected: Any, **kwargs: Any) -> EvaluationResult:
        """Check if output exactly matches expected."""
        expected_str = str(expected)

        output_cmp = output
        expected_cmp = expected_str

        if self.strip_whitespace:
            output_cmp = output_cmp.strip()
            expected_cmp = expected_cmp.strip()

        if not self.case_sensitive:
            output_cmp = output_cmp.lower()
            expected_cmp = expected_cmp.lower()

        success = output_cmp == expected_cmp

        return EvaluationResult(
            success=success,
            score=1.0 if success else 0.0,
            details={
                "output_length": len(output),
                "expected_length": len(expected_str),
                "case_sensitive": self.case_sensitive,
            },
        )


@register_evaluator("fuzzy_match")
class FuzzyMatchEvaluator(Evaluator):
    """Fuzzy string match using sequence similarity."""

    def __init__(self, threshold: float = 0.8, case_sensitive: bool = False):
        """Initialize fuzzy match evaluator.

        Args:
            threshold: Minimum similarity score (0-1) to consider a match
            case_sensitive: Whether comparison is case-sensitive
        """
        self.threshold = threshold
        self.case_sensitive = case_sensitive

    def evaluate(self, output: str, expected: Any, **kwargs: Any) -> EvaluationResult:
        """Check if output fuzzy-matches expected."""
        expected_str = str(expected)

        output_cmp = output.strip()
        expected_cmp = expected_str.strip()

        if not self.case_sensitive:
            output_cmp = output_cmp.lower()
            expected_cmp = expected_cmp.lower()

        # Calculate similarity ratio
        ratio = SequenceMatcher(None, output_cmp, expected_cmp).ratio()
        success = ratio >= self.threshold

        return EvaluationResult(
            success=success,
            score=ratio,
            details={
                "similarity": ratio,
                "threshold": self.threshold,
                "output_length": len(output),
                "expected_length": len(expected_str),
            },
        )


@register_evaluator("json_match")
class JSONMatchEvaluator(Evaluator):
    """JSON structure and value match evaluator."""

    def __init__(self, ignore_order: bool = True, strict_types: bool = False):
        """Initialize JSON match evaluator.

        Args:
            ignore_order: Whether to ignore array/object key order
            strict_types: Whether to require exact type matches
        """
        self.ignore_order = ignore_order
        self.strict_types = strict_types

    def evaluate(self, output: str, expected: Any, **kwargs: Any) -> EvaluationResult:
        """Check if output JSON matches expected JSON structure."""
        # Extract JSON from output (may be wrapped in markdown)
        output_json = self._extract_json(output)

        if output_json is None:
            return EvaluationResult(
                success=False,
                score=0.0,
                error="Could not parse JSON from output",
                details={"raw_output": output[:500]},
            )

        # Parse expected if it's a string
        if isinstance(expected, str):
            try:
                expected = json.loads(expected)
            except json.JSONDecodeError:
                return EvaluationResult(
                    success=False,
                    score=0.0,
                    error="Could not parse expected as JSON",
                )

        # Compare JSON structures
        score, details = self._compare_json(output_json, expected)
        success = score >= 0.99  # Allow tiny floating point differences

        return EvaluationResult(
            success=success,
            score=score,
            details=details,
        )

    def _extract_json(self, text: str) -> Any | None:
        """Extract JSON from text, handling markdown code blocks."""
        # Try direct parse first
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            pass

        # Try extracting from markdown code block
        patterns = [
            r"```json\s*([\s\S]*?)\s*```",
            r"```\s*([\s\S]*?)\s*```",
            r"\{[\s\S]*\}",
            r"\[[\s\S]*\]",
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    json_str = match.group(1) if "```" in pattern else match.group(0)
                    return json.loads(json_str.strip())
                except (json.JSONDecodeError, IndexError):
                    continue

        return None

    def _compare_json(
        self, output: Any, expected: Any, path: str = ""
    ) -> tuple[float, dict[str, Any]]:
        """Recursively compare JSON structures."""
        details: dict[str, Any] = {"path": path}

        # Type mismatch
        if type(output) != type(expected) and self.strict_types:
            return 0.0, {"error": f"Type mismatch at {path}", "output_type": type(output).__name__, "expected_type": type(expected).__name__}

        # Handle different types
        if isinstance(expected, dict):
            return self._compare_dicts(output, expected, path)
        elif isinstance(expected, list):
            return self._compare_lists(output, expected, path)
        elif isinstance(expected, (int, float)):
            # Numeric comparison with tolerance
            if not isinstance(output, (int, float)):
                try:
                    output = float(output)
                except (ValueError, TypeError):
                    return 0.0, {"error": f"Cannot convert to number at {path}"}

            if expected == 0:
                match = output == 0
            else:
                match = abs(output - expected) / abs(expected) < 0.0001
            return 1.0 if match else 0.0, details
        else:
            # String/bool comparison
            match = str(output).strip().lower() == str(expected).strip().lower()
            return 1.0 if match else 0.0, details

    def _compare_dicts(
        self, output: Any, expected: dict, path: str
    ) -> tuple[float, dict[str, Any]]:
        """Compare dictionary structures."""
        if not isinstance(output, dict):
            return 0.0, {"error": f"Expected dict at {path}, got {type(output).__name__}"}

        all_keys = set(expected.keys()) | set(output.keys())
        if not all_keys:
            return 1.0, {"matched_keys": 0}

        scores = []
        missing_keys = []
        extra_keys = []
        mismatched = []

        for key in expected.keys():
            if key not in output:
                missing_keys.append(key)
                scores.append(0.0)
            else:
                score, _ = self._compare_json(
                    output[key], expected[key], f"{path}.{key}"
                )
                scores.append(score)
                if score < 1.0:
                    mismatched.append(key)

        for key in output.keys():
            if key not in expected:
                extra_keys.append(key)

        avg_score = sum(scores) / len(scores) if scores else 1.0

        return avg_score, {
            "missing_keys": missing_keys,
            "extra_keys": extra_keys,
            "mismatched_keys": mismatched,
            "matched_keys": len(expected) - len(missing_keys) - len(mismatched),
        }

    def _compare_lists(
        self, output: Any, expected: list, path: str
    ) -> tuple[float, dict[str, Any]]:
        """Compare list structures."""
        if not isinstance(output, list):
            return 0.0, {"error": f"Expected list at {path}, got {type(output).__name__}"}

        if len(expected) == 0:
            return 1.0 if len(output) == 0 else 0.0, {"expected_length": 0, "output_length": len(output)}

        if len(output) != len(expected):
            # Length mismatch penalty
            length_penalty = min(len(output), len(expected)) / max(len(output), len(expected))
        else:
            length_penalty = 1.0

        scores = []
        for i, (out_item, exp_item) in enumerate(zip(output, expected)):
            score, _ = self._compare_json(out_item, exp_item, f"{path}[{i}]")
            scores.append(score)

        avg_score = (sum(scores) / len(scores)) * length_penalty if scores else length_penalty

        return avg_score, {
            "expected_length": len(expected),
            "output_length": len(output),
            "matched_items": sum(1 for s in scores if s >= 0.99),
        }


@register_evaluator("ast_match")
class ASTMatchEvaluator(Evaluator):
    """AST-based function call match evaluator for BFCL-style tasks."""

    def __init__(self, allow_extra_args: bool = False):
        """Initialize AST match evaluator.

        Args:
            allow_extra_args: Whether to allow extra arguments not in expected
        """
        self.allow_extra_args = allow_extra_args
        self._json_evaluator = JSONMatchEvaluator(ignore_order=True)

    def evaluate(self, output: str, expected: Any, **kwargs: Any) -> EvaluationResult:
        """Check if function call matches expected."""
        # Extract function call from output
        func_call = self._extract_function_call(output)

        if func_call is None:
            return EvaluationResult(
                success=False,
                score=0.0,
                error="Could not parse function call from output",
                details={"raw_output": output[:500]},
            )

        # Parse expected if needed
        expected_calls = self._normalize_expected(expected)

        if not expected_calls:
            return EvaluationResult(
                success=False,
                score=0.0,
                error="Could not parse expected function calls",
            )

        # Try to match against any expected call
        best_score = 0.0
        best_details: dict[str, Any] = {}

        for exp_call in expected_calls:
            score, details = self._compare_function_call(func_call, exp_call)
            if score > best_score:
                best_score = score
                best_details = details

        success = best_score >= 0.99

        return EvaluationResult(
            success=success,
            score=best_score,
            details=best_details,
        )

    def _extract_function_call(self, text: str) -> dict[str, Any] | None:
        """Extract function call from text."""
        # Try JSON extraction first
        json_result = self._json_evaluator._extract_json(text)

        if json_result is not None:
            # Normalize to {name, arguments} format
            if isinstance(json_result, dict):
                if "name" in json_result:
                    return json_result
                # Maybe it's {function_name: {args}}
                if len(json_result) == 1:
                    name = list(json_result.keys())[0]
                    args = json_result[name]
                    return {"name": name, "arguments": args if isinstance(args, dict) else {}}

            # Maybe it's a list of calls
            if isinstance(json_result, list) and json_result:
                first = json_result[0]
                if isinstance(first, dict) and "name" in first:
                    return first

        return None

    def _normalize_expected(self, expected: Any) -> list[dict[str, Any]]:
        """Normalize expected to list of {name, arguments} dicts.

        Handles BFCL format: [{func_name: {arg: [possible_values]}}]
        """
        if isinstance(expected, str):
            try:
                expected = json.loads(expected)
            except json.JSONDecodeError:
                return []

        if isinstance(expected, dict):
            if "name" in expected:
                return [expected]
            # BFCL format: {"function_name": {"arg": "value"}}
            return [{"name": k, "arguments": v} for k, v in expected.items() if isinstance(v, dict)]

        if isinstance(expected, list):
            result = []
            for item in expected:
                if isinstance(item, dict):
                    if "name" in item:
                        result.append(item)
                    else:
                        # BFCL format: {func_name: {arg: [possible_values]}}
                        for func_name, args in item.items():
                            if isinstance(args, dict):
                                result.append({"name": func_name, "arguments": args})
            return result

        return []

    def _compare_function_call(
        self, output: dict[str, Any], expected: dict[str, Any]
    ) -> tuple[float, dict[str, Any]]:
        """Compare function call structures."""
        details: dict[str, Any] = {}

        # Check function name
        out_name = output.get("name", "")
        exp_name = expected.get("name", "")

        if out_name != exp_name:
            return 0.0, {
                "error": "Function name mismatch",
                "output_name": out_name,
                "expected_name": exp_name,
            }

        details["function_name"] = out_name

        # Check arguments
        out_args = output.get("arguments", {})
        exp_args = expected.get("arguments", {})

        if not isinstance(out_args, dict):
            try:
                out_args = json.loads(out_args) if isinstance(out_args, str) else {}
            except json.JSONDecodeError:
                out_args = {}

        if not isinstance(exp_args, dict):
            try:
                exp_args = json.loads(exp_args) if isinstance(exp_args, str) else {}
            except json.JSONDecodeError:
                exp_args = {}

        # Compare arguments - handle BFCL format where values are lists of acceptable values
        score, arg_details = self._compare_bfcl_args(out_args, exp_args)
        details["arguments"] = arg_details

        return score, details

    def _compare_bfcl_args(
        self, output_args: dict[str, Any], expected_args: dict[str, Any]
    ) -> tuple[float, dict[str, Any]]:
        """Compare arguments, handling BFCL format where expected values are lists.

        BFCL format: {arg_name: [list_of_acceptable_values]}
        """
        if not expected_args:
            return 1.0 if not output_args else 0.5, {"matched": 0, "total": 0}

        matched = 0
        total = len(expected_args)
        mismatched = []
        missing = []

        for arg_name, exp_values in expected_args.items():
            if arg_name not in output_args:
                missing.append(arg_name)
                continue

            out_value = output_args[arg_name]

            # BFCL format: exp_values is a list of acceptable values
            if isinstance(exp_values, list):
                # Check if output matches any acceptable value
                if self._value_in_list(out_value, exp_values):
                    matched += 1
                else:
                    mismatched.append(arg_name)
            else:
                # Direct comparison
                if self._values_equal(out_value, exp_values):
                    matched += 1
                else:
                    mismatched.append(arg_name)

        score = matched / total if total > 0 else 1.0

        return score, {
            "matched": matched,
            "total": total,
            "missing": missing,
            "mismatched": mismatched,
        }

    def _value_in_list(self, value: Any, acceptable: list[Any]) -> bool:
        """Check if value matches any in the acceptable list."""
        for acc in acceptable:
            if self._values_equal(value, acc):
                return True
        return False

    def _values_equal(self, a: Any, b: Any) -> bool:
        """Check if two values are equal (with type coercion)."""
        # Direct equality
        if a == b:
            return True

        # Empty string matches None/empty
        if (a == "" or a is None) and (b == "" or b is None):
            return True

        # String comparison (case-insensitive for strings)
        if isinstance(a, str) and isinstance(b, str):
            return a.strip().lower() == b.strip().lower()

        # Numeric comparison
        try:
            num_a = float(a) if not isinstance(a, bool) else None
            num_b = float(b) if not isinstance(b, bool) else None
            if num_a is not None and num_b is not None:
                return abs(num_a - num_b) < 0.0001
        except (ValueError, TypeError):
            pass

        # String representation comparison
        return str(a).strip().lower() == str(b).strip().lower()


@register_evaluator("schema")
class SchemaEvaluator(Evaluator):
    """JSON Schema validation evaluator."""

    def __init__(self, require_all_fields: bool = False):
        """Initialize schema evaluator.

        Args:
            require_all_fields: Whether all expected fields must be present
        """
        self.require_all_fields = require_all_fields
        self._json_evaluator = JSONMatchEvaluator()

    def evaluate(self, output: str, expected: Any, **kwargs: Any) -> EvaluationResult:
        """Validate output against expected schema/fields."""
        # Extract JSON from output
        output_json = self._json_evaluator._extract_json(output)

        if output_json is None:
            return EvaluationResult(
                success=False,
                score=0.0,
                error="Could not parse JSON from output",
                details={"raw_output": output[:500]},
            )

        # If expected is a dict, do field-by-field comparison
        if isinstance(expected, dict):
            return self._compare_fields(output_json, expected)

        # If expected is a list (line items), compare list structures
        if isinstance(expected, list):
            return self._compare_list_items(output_json, expected)

        return EvaluationResult(
            success=False,
            score=0.0,
            error=f"Unsupported expected type: {type(expected).__name__}",
        )

    def _compare_fields(
        self, output: Any, expected: dict[str, Any]
    ) -> EvaluationResult:
        """Compare extracted fields against expected."""
        if not isinstance(output, dict):
            return EvaluationResult(
                success=False,
                score=0.0,
                error=f"Expected dict output, got {type(output).__name__}",
            )

        matched = 0
        total = len(expected)
        missing = []
        wrong = []

        for key, exp_value in expected.items():
            if key not in output:
                missing.append(key)
            elif self._values_match(output[key], exp_value):
                matched += 1
            else:
                wrong.append(key)

        score = matched / total if total > 0 else 1.0
        success = matched == total if self.require_all_fields else score >= 0.5

        return EvaluationResult(
            success=success,
            score=score,
            details={
                "matched_fields": matched,
                "total_fields": total,
                "missing_fields": missing,
                "wrong_fields": wrong,
            },
        )

    def _compare_list_items(
        self, output: Any, expected: list[dict[str, Any]]
    ) -> EvaluationResult:
        """Compare list of items (e.g., line items)."""
        if not isinstance(output, list):
            return EvaluationResult(
                success=False,
                score=0.0,
                error=f"Expected list output, got {type(output).__name__}",
            )

        if len(expected) == 0:
            return EvaluationResult(
                success=len(output) == 0,
                score=1.0 if len(output) == 0 else 0.0,
                details={"expected_count": 0, "output_count": len(output)},
            )

        # Simple length-based scoring for now
        length_score = min(len(output), len(expected)) / max(len(output), len(expected))

        return EvaluationResult(
            success=length_score >= 0.8,
            score=length_score,
            details={
                "expected_count": len(expected),
                "output_count": len(output),
            },
        )

    def _values_match(self, output_val: Any, expected_val: Any) -> bool:
        """Check if two values match (with type coercion)."""
        # Exact match
        if output_val == expected_val:
            return True

        # String comparison (case-insensitive, stripped)
        out_str = str(output_val).strip().lower()
        exp_str = str(expected_val).strip().lower()

        if out_str == exp_str:
            return True

        # Numeric comparison
        try:
            out_num = float(output_val)
            exp_num = float(expected_val)
            if exp_num == 0:
                return out_num == 0
            return abs(out_num - exp_num) / abs(exp_num) < 0.01
        except (ValueError, TypeError):
            pass

        return False
