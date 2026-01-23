"""Base dataset converter - defines the generic structure all datasets convert to."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class DatasetInstance:
    """The ONE format all datasets convert to. No exceptions.

    After conversion, everything is generic:
    - Baseline receives `input` + `output_format` + `context`, compiles workflow
    - Evaluation uses LLM to compare output against `expected_output` semantically

    Key separation:
    - `output_format`: Structure description (NO values) - tells workflow WHAT shape to output
    - `expected_output`: Ground truth values - used ONLY for evaluation, never seen during compilation

    The `context` dict enables task signature grouping:
    - Tasks with same context schema share compiled workflows
    - The `input` varies per instance, `context` defines the task type
    """

    id: str
    input: str  # The varying part (user query, specific values)
    output_format: dict = field(default_factory=dict)  # Structure description (NO values)
    expected_output: Any = None  # Ground truth for evaluation
    context: dict = field(default_factory=dict)  # Structured context for signature grouping
    possible_outputs: list[Any] = field(default_factory=list)  # Deprecated, kept for compatibility

    def matches(self, output: Any) -> bool:
        """Check if output matches any possible output.

        Handles cases where:
        - Output is a single value matching one possible output
        - Output is a list containing items from possible outputs
        - Output is a list and possible_outputs are individual items
        """
        # Normalize output for comparison
        output_normalized = self._normalize(output)

        # If output is a list, check if ANY expected output is in it
        # This handles workflows returning [func_call1, func_call2, ...]
        if isinstance(output_normalized, list):
            for expected in self.possible_outputs:
                expected_norm = self._normalize(expected)
                # Check if expected is in the output list
                for output_item in output_normalized:
                    if self._values_match(output_item, expected_norm):
                        return True

        # Standard comparison: output matches any possible output directly
        for expected in self.possible_outputs:
            if self._values_match(output_normalized, self._normalize(expected)):
                return True

        return False

    def _normalize(self, value: Any) -> Any:
        """Normalize value for comparison."""
        if isinstance(value, str):
            import json
            import ast

            value = value.strip()

            # Try JSON first (double quotes)
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                pass

            # Try Python literal (single quotes) - handles str() output
            try:
                return ast.literal_eval(value)
            except (ValueError, SyntaxError):
                pass

            # Fallback to lowercase string
            return value.lower()

        return value

    def _values_match(self, a: Any, b: Any) -> bool:
        """Check if two values match."""
        # Direct equality
        if a == b:
            return True

        # String comparison (case-insensitive)
        if isinstance(a, str) and isinstance(b, str):
            return a.lower().strip() == b.lower().strip()

        # Dict comparison
        if isinstance(a, dict) and isinstance(b, dict):
            if set(a.keys()) != set(b.keys()):
                return False
            return all(self._values_match(a[k], b[k]) for k in a)

        # List comparison
        if isinstance(a, list) and isinstance(b, list):
            if len(a) != len(b):
                return False
            return all(self._values_match(x, y) for x, y in zip(a, b))

        # Numeric comparison
        try:
            if float(a) == float(b):
                return True
        except (TypeError, ValueError):
            pass

        return False


class DatasetConverter(ABC):
    """Base class for dataset converters.

    Each converter takes raw dataset files and produces DatasetInstance objects.
    All the complexity of parsing different formats stays HERE.
    """

    @abstractmethod
    def convert(self, raw_data: dict) -> list[DatasetInstance]:
        """Convert raw dataset to list of DatasetInstance.

        Args:
            raw_data: Raw dataset in whatever format it comes in

        Returns:
            List of DatasetInstance with {id, input, output_format, expected_output, context}
        """
        ...

    @abstractmethod
    def load_file(self, path: str) -> list[DatasetInstance]:
        """Load dataset from file path.

        Args:
            path: Path to dataset file(s)

        Returns:
            List of DatasetInstance
        """
        ...
