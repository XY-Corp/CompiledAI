"""Concrete evaluator implementations."""

import json
import re
from difflib import SequenceMatcher
from typing import Any

from .base import EvaluationResult, Evaluator, register_evaluator


def _normalize_string(s: str) -> str:
    """Normalize string for comparison by removing commas and periods.

    This helps ignore punctuation differences like "123 Main St." vs "123 Main St"
    or "New York, NY" vs "New York NY".
    """
    return s.replace(',', '').replace('.', '').strip()


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
            # String/bool comparison (normalize to ignore commas and periods)
            out_normalized = _normalize_string(str(output).lower())
            exp_normalized = _normalize_string(str(expected).lower())
            match = out_normalized == exp_normalized
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

        # String comparison (case-insensitive, normalize punctuation)
        if isinstance(a, str) and isinstance(b, str):
            return _normalize_string(a.lower()) == _normalize_string(b.lower())

        # Numeric comparison
        try:
            num_a = float(a) if not isinstance(a, bool) else None
            num_b = float(b) if not isinstance(b, bool) else None
            if num_a is not None and num_b is not None:
                return abs(num_a - num_b) < 0.0001
        except (ValueError, TypeError):
            pass

        # String representation comparison (normalized punctuation)
        return _normalize_string(str(a).lower()) == _normalize_string(str(b).lower())


@register_evaluator("bfcl_function_call")
class BFCLFunctionCallEvaluator(Evaluator):
    """BFCL function call evaluator for Code Factory output.

    Designed to evaluate Code Factory's BFCLResult against BFCL ground truth.
    Handles BFCL's format where ground truth allows multiple valid answers:
    [{"function_name": {"param1": [valid_value1, valid_value2], ...}}]
    """

    def __init__(self, strict_params: bool = False):
        """Initialize BFCL function call evaluator.

        Args:
            strict_params: Require exact parameter match (no missing optional params)
        """
        self.strict_params = strict_params

    def evaluate(self, output: str, expected: Any, **kwargs: Any) -> EvaluationResult:
        """Evaluate function call against BFCL ground truth.

        Args:
            output: JSON string with function call (from Code Factory)
            expected: BFCL ground truth (list of acceptable function calls)
            **kwargs: Additional context

        Returns:
            EvaluationResult with success, score, and details
        """
        # Parse output
        predicted = self._parse_output(output)
        if predicted is None:
            return EvaluationResult(
                success=False,
                score=0.0,
                error="Could not parse function call from output",
                details={"raw_output": output[:500]},
            )

        # Parse expected (BFCL ground truth format)
        ground_truth = self._parse_ground_truth(expected)
        if not ground_truth:
            return EvaluationResult(
                success=False,
                score=0.0,
                error="Could not parse ground truth",
                details={"raw_expected": str(expected)[:500]},
            )

        # Compare against all valid answers
        best_score = 0.0
        best_details: dict[str, Any] = {}

        for acceptable in ground_truth:
            success, score, details = self._compare_function_call(predicted, acceptable)
            if score > best_score:
                best_score = score
                best_details = details
                if success:
                    break  # Found a match, no need to continue

        overall_success = best_score >= 0.99

        return EvaluationResult(
            success=overall_success,
            score=best_score,
            details=best_details,
        )

    def _parse_output(self, text: str) -> dict[str, Any] | None:
        """Parse function call from output text.

        Handles multiple formats:
        - {"function_name": {"args"}}  (BFCL native)
        - {"name": "...", "arguments": {...}}  (OpenAI-style)
        - {"function_name": "...", "arguments": {...}}  (Code Factory style)
        """
        if isinstance(text, dict):
            return self._normalize_function_call(text)

        try:
            data = json.loads(text.strip())
            return self._normalize_function_call(data)
        except json.JSONDecodeError:
            pass

        # Try extracting from markdown code blocks
        patterns = [
            r"```json\s*([\s\S]*?)\s*```",
            r"```\s*([\s\S]*?)\s*```",
            r"\{[\s\S]*\}",
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    json_str = match.group(1) if "```" in pattern else match.group(0)
                    data = json.loads(json_str.strip())
                    return self._normalize_function_call(data)
                except (json.JSONDecodeError, IndexError):
                    continue

        return None

    def _normalize_function_call(self, data: Any) -> dict[str, Any] | None:
        """Normalize various function call formats to {name, arguments}."""
        if not isinstance(data, dict):
            return None

        # Format 1: {"function_name": "...", "arguments": {...}} (Code Factory)
        if "function_name" in data:
            return {
                "name": data["function_name"],
                "arguments": data.get("arguments", {}),
            }

        # Format 2: {"name": "...", "arguments": {...}} (OpenAI-style)
        if "name" in data:
            return {
                "name": data["name"],
                "arguments": data.get("arguments", data.get("parameters", {})),
            }

        # Format 3: {"func_name": {...args...}} (BFCL native)
        if len(data) == 1:
            func_name = list(data.keys())[0]
            args = data[func_name]
            if isinstance(args, dict):
                return {"name": func_name, "arguments": args}

        return None

    def _parse_ground_truth(self, expected: Any) -> list[dict[str, Any]]:
        """Parse BFCL ground truth format.

        BFCL format: [{"function_name": {"param1": [valid_values], "param2": [valid_values]}}]
        """
        if isinstance(expected, str):
            try:
                expected = json.loads(expected)
            except json.JSONDecodeError:
                return []

        if isinstance(expected, dict):
            # Single function call
            if "ground_truth" in expected:
                return self._parse_ground_truth(expected["ground_truth"])
            return [expected]

        if isinstance(expected, list):
            return expected

        return []

    def _compare_function_call(
        self, predicted: dict[str, Any], acceptable: dict[str, Any]
    ) -> tuple[bool, float, dict]:
        """Compare predicted function call against one acceptable answer.

        Args:
            predicted: Normalized {name, arguments}
            acceptable: BFCL format {func_name: {param: [valid_values]}}

        Returns:
            Tuple of (success, score, details)
        """
        details = {
            "predicted_function": predicted.get("name", ""),
            "predicted_arguments": predicted.get("arguments", {}),
        }

        # Extract expected function name and args from BFCL format
        if not acceptable:
            return False, 0.0, {"error": "Empty acceptable answer"}

        expected_name = list(acceptable.keys())[0]
        expected_args = acceptable.get(expected_name, {})

        details["expected_function"] = expected_name
        details["expected_arguments"] = expected_args

        # Check function name
        if predicted.get("name", "") != expected_name:
            return False, 0.0, {
                **details,
                "error": "Function name mismatch",
            }

        # Check arguments
        pred_args = predicted.get("arguments", {})
        args_score, args_details = self._compare_bfcl_arguments(pred_args, expected_args)

        details["argument_match"] = args_details

        success = args_score >= 0.99
        return success, args_score, details

    def _compare_bfcl_arguments(
        self, predicted: dict[str, Any], expected: dict[str, Any]
    ) -> tuple[float, dict]:
        """Compare arguments against BFCL format.

        BFCL expected format: {"param_name": [list_of_valid_values]}
        Empty string "" in valid values means "optional, any value OK"
        """
        if not expected:
            return 1.0, {"matched": 0, "total": 0}

        matched = 0
        total = len(expected)
        mismatched = []
        missing = []

        for param_name, valid_values in expected.items():
            if param_name not in predicted:
                # Check if it's optional (empty string in valid values)
                if isinstance(valid_values, list) and "" in valid_values:
                    matched += 0.5  # Partial credit for omitting optional
                else:
                    missing.append(param_name)
                continue

            pred_value = predicted[param_name]

            # valid_values is a list of acceptable values
            if isinstance(valid_values, list):
                if self._value_matches_any(pred_value, valid_values):
                    matched += 1
                else:
                    mismatched.append({
                        "param": param_name,
                        "predicted": pred_value,
                        "expected_values": valid_values,
                    })
            else:
                # Direct comparison
                if self._values_equivalent(pred_value, valid_values):
                    matched += 1
                else:
                    mismatched.append({
                        "param": param_name,
                        "predicted": pred_value,
                        "expected": valid_values,
                    })

        score = matched / total if total > 0 else 1.0

        return score, {
            "matched": matched,
            "total": total,
            "missing": missing,
            "mismatched": mismatched,
        }

    def _value_matches_any(self, predicted: Any, valid_values: list) -> bool:
        """Check if predicted value matches any valid value."""
        for valid in valid_values:
            if valid == "":
                # Empty string means optional - any non-None value is OK
                if predicted is not None:
                    return True
                continue

            if self._values_equivalent(predicted, valid):
                return True

        return False

    def _values_equivalent(self, a: Any, b: Any) -> bool:
        """Check if two values are equivalent (with type coercion)."""
        # Direct equality
        if a == b:
            return True

        # None/empty equivalence
        if (a is None or a == "") and (b is None or b == ""):
            return True

        # Numeric equivalence (5 == 5.0)
        try:
            if not isinstance(a, bool) and not isinstance(b, bool):
                num_a = float(a)
                num_b = float(b)
                return abs(num_a - num_b) < 0.0001
        except (TypeError, ValueError):
            pass

        # String equivalence (case-insensitive, normalized)
        if isinstance(a, str) and isinstance(b, str):
            return _normalize_string(a.lower()) == _normalize_string(b.lower())

        # List equivalence (order-sensitive)
        if isinstance(a, list) and isinstance(b, list):
            if len(a) != len(b):
                return False
            return all(self._values_equivalent(x, y) for x, y in zip(a, b))

        # Dict equivalence
        if isinstance(a, dict) and isinstance(b, dict):
            if set(a.keys()) != set(b.keys()):
                return False
            return all(self._values_equivalent(a[k], b[k]) for k in a)

        # String representation as last resort
        return _normalize_string(str(a).lower()) == _normalize_string(str(b).lower())


@register_evaluator("schema")
class SchemaEvaluator(Evaluator):
    """JSON Schema validation evaluator."""

    def __init__(self, require_all_fields: bool = True):
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

        # Normalize expected if it's a string (may have single quotes)
        if isinstance(expected, str):
            try:
                # Try to parse as JSON
                expected = json.loads(expected)
            except json.JSONDecodeError:
                # If that fails, try to parse as Python literal (handles single quotes)
                try:
                    import ast
                    expected = ast.literal_eval(expected)
                except (ValueError, SyntaxError):
                    pass  # Keep as string

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

        # Recursive dict comparison
        if isinstance(expected_val, dict):
            if not isinstance(output_val, dict):
                return False
            # Check all expected keys exist and match
            for key, exp_v in expected_val.items():
                if key not in output_val:
                    return False
                if not self._values_match(output_val[key], exp_v):
                    return False
            return True

        # Recursive list comparison
        if isinstance(expected_val, list):
            if not isinstance(output_val, list):
                return False
            if len(output_val) != len(expected_val):
                return False
            for out_v, exp_v in zip(output_val, expected_val):
                if not self._values_match(out_v, exp_v):
                    return False
            return True

        # String comparison (case-insensitive, normalized punctuation)
        out_str = _normalize_string(str(output_val).lower())
        exp_str = _normalize_string(str(expected_val).lower())

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


@register_evaluator("llm")
class LLMEvaluator(Evaluator):
    """LLM-based semantic evaluator using Claude haiku.

    Compares output against expected semantically, returning match types:
    - total_match: Both format AND content match
    - content_match: Content is correct but format differs
    - format_match: Format is correct but content is wrong
    - failure: Neither format nor content matches
    """

    def __init__(self, model: str = "claude-3-5-haiku-latest"):
        """Initialize LLM evaluator.

        Args:
            model: Model to use for evaluation (default: haiku for speed/cost)
        """
        self.model = model
        self._client = None

    @property
    def client(self):
        """Lazy-load Anthropic client."""
        if self._client is None:
            import anthropic
            self._client = anthropic.Anthropic()
        return self._client

    def evaluate(self, output: str, expected: Any, **kwargs: Any) -> EvaluationResult:
        """Evaluate output against expected using LLM.

        Args:
            output: The actual output from the workflow
            expected: The expected ground truth values
            output_format: (optional) The expected output structure description
            **kwargs: Additional context

        Returns:
            EvaluationResult with match type (total_match, content_match, format_match, failure)
        """
        output_format = kwargs.get("output_format", {})

        # Build evaluation prompt
        prompt = self._build_prompt(output, expected, output_format)

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )

            # Parse LLM response
            result_text = response.content[0].text
            return self._parse_response(result_text, output, expected)

        except Exception as e:
            return EvaluationResult(
                success=False,
                score=0.0,
                error=f"LLM evaluation failed: {str(e)}",
                details={"raw_output": str(output)[:500]},
            )

    def _build_prompt(self, output: Any, expected: Any, output_format: dict) -> str:
        """Build the evaluation prompt for the LLM."""
        # Normalize to JSON strings for consistent comparison
        if isinstance(output, str):
            try:
                output_json = json.loads(output)
                output_str = json.dumps(output_json, indent=2)
            except json.JSONDecodeError:
                output_str = output
        else:
            output_str = json.dumps(output, indent=2) if output else str(output)

        if isinstance(expected, str):
            try:
                expected_json = json.loads(expected)
                expected_str = json.dumps(expected_json, indent=2)
            except json.JSONDecodeError:
                expected_str = expected
        else:
            expected_str = json.dumps(expected, indent=2) if expected else str(expected)

        format_str = json.dumps(output_format, indent=2) if output_format else "Not specified"

        return f"""Compare the ACTUAL OUTPUT against the EXPECTED OUTPUT and determine the match type.

EXPECTED OUTPUT FORMAT (structure description):
{format_str}

EXPECTED OUTPUT (ground truth values):
{expected_str}

ACTUAL OUTPUT:
{output_str}

Evaluate both FORMAT (structure/fields) and CONTENT (values):

FORMAT match criteria:
- Has the correct fields/keys
- Has the correct data types
- Follows the expected structure

CONTENT match criteria:
- Values are semantically equivalent (minor formatting differences OK)
- Numbers match (5 == 5.0, "5" == 5)
- Strings match case-insensitively, ignoring trailing punctuation
- Dates/times represent the same moment

Return your evaluation as JSON:
{{
  "match_type": "total_match" | "content_match" | "format_match" | "failure",
  "format_correct": true | false,
  "content_correct": true | false,
  "field_matches": {{"field_name": true/false, ...}},
  "explanation": "Brief explanation of what matched/didn't match"
}}

Rules:
- total_match: Format AND content both correct
- content_match: Content is correct but format differs (e.g., extra fields, different structure)
- format_match: Format is correct but content/values are wrong
- failure: Neither format nor content is correct

Return ONLY the JSON, no other text."""

    def _parse_response(self, response_text: str, output: Any, expected: Any) -> EvaluationResult:
        """Parse the LLM's response into an EvaluationResult."""
        try:
            # Try to extract JSON from response
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if not json_match:
                raise ValueError("No JSON found in response")

            result = json.loads(json_match.group())

            match_type = result.get("match_type", "failure")
            format_correct = result.get("format_correct", False)
            content_correct = result.get("content_correct", False)
            field_matches = result.get("field_matches", {})
            explanation = result.get("explanation", "")

            # Map match type to score
            score_map = {
                "total_match": 1.0,
                "content_match": 0.8,
                "format_match": 0.3,
                "failure": 0.0,
            }
            score = score_map.get(match_type, 0.0)

            # Success only for total_match or content_match
            success = match_type in ("total_match", "content_match")

            return EvaluationResult(
                success=success,
                score=score,
                details={
                    "match_type": match_type,
                    "format_correct": format_correct,
                    "content_correct": content_correct,
                    "field_matches": field_matches,
                    "explanation": explanation,
                },
            )

        except (json.JSONDecodeError, ValueError) as e:
            # Fallback to heuristic parsing if JSON parsing fails
            response_lower = response_text.lower()

            if "total_match" in response_lower or ("format" in response_lower and "content" in response_lower and "correct" in response_lower):
                return EvaluationResult(success=True, score=1.0, details={"match_type": "total_match", "raw_response": response_text[:500]})
            elif "content_match" in response_lower or "content correct" in response_lower:
                return EvaluationResult(success=True, score=0.8, details={"match_type": "content_match", "raw_response": response_text[:500]})
            elif "format_match" in response_lower or "format correct" in response_lower:
                return EvaluationResult(success=False, score=0.3, details={"match_type": "format_match", "raw_response": response_text[:500]})
            else:
                return EvaluationResult(success=False, score=0.0, details={"match_type": "failure", "raw_response": response_text[:500], "parse_error": str(e)})
