"""Standardized task format for cross-dataset compatibility.

All datasets are converted to this common format to enable:
- Unified evaluation across datasets
- Consistent baseline interface
- Simplified comparison between datasets
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class EvaluationType(str, Enum):
    """How to evaluate outputs against valid_outputs."""

    EXACT = "exact"           # Exact string match
    JSON = "json"             # JSON equivalence (order-independent)
    AST = "ast"               # AST/function call matching
    SEMANTIC = "semantic"     # Semantic similarity
    SCHEMA = "schema"         # JSON schema validation
    REGEX = "regex"           # Regex pattern match
    CONTAINS = "contains"     # Output contains expected
    CUSTOM = "custom"         # Custom evaluation function


@dataclass
class StandardizedInstance:
    """A single standardized test instance.

    This is the common format that all dataset instances are converted to,
    enabling unified evaluation and baseline execution.

    Attributes:
        instance_id: Unique identifier for this instance
        input: The main input text/prompt to be processed
        context: Additional context needed for the task (functions, schema, etc.)
        valid_outputs: List of acceptable outputs (multiple valid answers supported)
        evaluation_type: How to compare actual output against valid_outputs
        metadata: Additional information (source dataset, difficulty, etc.)
    """

    instance_id: str
    input: str
    context: dict[str, Any] = field(default_factory=dict)
    valid_outputs: list[Any] = field(default_factory=list)
    evaluation_type: EvaluationType = EvaluationType.EXACT
    metadata: dict[str, Any] = field(default_factory=dict)

    def matches_output(self, output: Any) -> bool:
        """Check if output matches any valid output.

        Basic implementation - use Evaluator classes for full evaluation.

        Args:
            output: The actual output to check

        Returns:
            True if output matches any valid_output
        """
        if not self.valid_outputs:
            return True  # No expected output to compare

        if self.evaluation_type == EvaluationType.EXACT:
            return any(str(output) == str(vo) for vo in self.valid_outputs)
        elif self.evaluation_type == EvaluationType.CONTAINS:
            output_str = str(output).lower()
            return any(str(vo).lower() in output_str for vo in self.valid_outputs)
        else:
            # For complex evaluation types, defer to evaluators
            return False


@dataclass
class StandardizedTask:
    """A standardized benchmark task with multiple instances.

    Attributes:
        task_id: Unique identifier for this task
        name: Human-readable task name
        description: What this task tests
        category: Task category (e.g., function_calling, document_processing)
        difficulty: Task difficulty (simple, medium, complex)
        instances: List of standardized test instances
        default_evaluation: Default evaluation type for instances
        tags: Tags for filtering
        source: Original dataset source
    """

    task_id: str
    name: str
    description: str
    category: str
    difficulty: str
    instances: list[StandardizedInstance] = field(default_factory=list)
    default_evaluation: EvaluationType = EvaluationType.EXACT
    tags: list[str] = field(default_factory=list)
    source: str = ""


@dataclass
class StandardizedDataset:
    """A standardized dataset with unified task format.

    Attributes:
        name: Dataset name
        description: Dataset description
        version: Dataset version
        tasks: List of standardized tasks
        metadata: Additional dataset metadata
    """

    name: str
    description: str
    version: str
    tasks: list[StandardizedTask] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def total_instances(self) -> int:
        """Total number of instances across all tasks."""
        return sum(len(t.instances) for t in self.tasks)

    def filter_by_category(self, category: str) -> list[StandardizedTask]:
        """Filter tasks by category."""
        return [t for t in self.tasks if t.category == category]

    def filter_by_tags(self, tags: list[str]) -> list[StandardizedTask]:
        """Filter tasks by tags (any match)."""
        return [t for t in self.tasks if any(tag in t.tags for tag in tags)]
