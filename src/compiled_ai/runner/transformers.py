"""Dataset transformers convert various formats to StandardizedDataset.

Each transformer handles a specific dataset format and converts it to
the common StandardizedInstance format with input, context, and valid_outputs.
"""

import json
from abc import ABC, abstractmethod
from typing import Any

from .dataset import Dataset, Task, TaskInstance
from .standardized import (
    EvaluationType,
    StandardizedDataset,
    StandardizedInstance,
    StandardizedTask,
)


class DatasetTransformer(ABC):
    """Base class for dataset format transformers."""

    name: str = "base"

    @abstractmethod
    def transform(self, dataset: Dataset) -> StandardizedDataset:
        """Transform a dataset to standardized format.

        Args:
            dataset: Original dataset in native format

        Returns:
            StandardizedDataset with unified format
        """
        ...

    def transform_instance(
        self, instance: TaskInstance, task: Task
    ) -> StandardizedInstance:
        """Transform a single task instance.

        Override this for dataset-specific transformations.

        Args:
            instance: Original task instance
            task: Parent task for context

        Returns:
            StandardizedInstance
        """
        # Build input from prompt template
        input_text = task.prompt_template.format(**instance.input_data)

        return StandardizedInstance(
            instance_id=instance.instance_id,
            input=input_text,
            context=instance.input_data,
            valid_outputs=[instance.expected_output] if instance.expected_output else [],
            evaluation_type=self._map_evaluation_type(task.evaluation_type),
            metadata={
                "task_id": task.task_id,
                "source": task.source,
                **instance.metadata,
            },
        )

    def _map_evaluation_type(self, eval_type: str) -> EvaluationType:
        """Map dataset evaluation type to standardized enum."""
        mapping = {
            "exact_match": EvaluationType.EXACT,
            "exact": EvaluationType.EXACT,
            "json": EvaluationType.JSON,
            "ast_match": EvaluationType.AST,
            "ast": EvaluationType.AST,
            "semantic": EvaluationType.SEMANTIC,
            "schema": EvaluationType.SCHEMA,
            "regex": EvaluationType.REGEX,
            "contains": EvaluationType.CONTAINS,
            "milestone": EvaluationType.CUSTOM,
            "custom": EvaluationType.CUSTOM,
        }
        return mapping.get(eval_type, EvaluationType.EXACT)


class XYBenchmarkTransformer(DatasetTransformer):
    """Transformer for XY Benchmark native format."""

    name = "xy_benchmark"

    def transform(self, dataset: Dataset) -> StandardizedDataset:
        """Transform XY Benchmark dataset."""
        tasks = []

        for task in dataset.tasks:
            instances = [
                self.transform_instance(inst, task) for inst in task.instances
            ]

            tasks.append(
                StandardizedTask(
                    task_id=task.task_id,
                    name=task.name,
                    description=task.description,
                    category=task.category.value,
                    difficulty=task.difficulty.value,
                    instances=instances,
                    default_evaluation=self._map_evaluation_type(task.evaluation_type),
                    tags=task.tags,
                    source="xy_benchmark",
                )
            )

        return StandardizedDataset(
            name=dataset.name,
            description=dataset.description,
            version=dataset.version,
            tasks=tasks,
            metadata=dataset.metadata,
        )


class BFCLTransformer(DatasetTransformer):
    """Transformer for Berkeley Function Calling Leaderboard format.

    BFCL format:
    - input_data: {"user_query": str, "functions": str (JSON)}
    - expected_output: list of valid function calls

    Standardized format:
    - input: user_query
    - context: {"functions": parsed JSON list}
    - valid_outputs: list of valid function call representations
    """

    name = "bfcl"

    def transform(self, dataset: Dataset) -> StandardizedDataset:
        """Transform BFCL dataset to standardized format."""
        tasks = []

        for task in dataset.tasks:
            instances = [
                self.transform_instance(inst, task) for inst in task.instances
            ]

            tasks.append(
                StandardizedTask(
                    task_id=task.task_id,
                    name=task.name,
                    description=task.description,
                    category=task.category.value,
                    difficulty=task.difficulty.value,
                    instances=instances,
                    default_evaluation=EvaluationType.AST,
                    tags=task.tags,
                    source="bfcl",
                )
            )

        return StandardizedDataset(
            name=dataset.name,
            description=dataset.description,
            version=dataset.version,
            tasks=tasks,
            metadata=dataset.metadata,
        )

    def transform_instance(
        self, instance: TaskInstance, task: Task
    ) -> StandardizedInstance:
        """Transform BFCL instance with function calling context."""
        input_data = instance.input_data
        user_query = input_data.get("user_query", "")

        # Parse functions JSON string back to list
        functions_str = input_data.get("functions", "[]")
        try:
            functions = (
                json.loads(functions_str)
                if isinstance(functions_str, str)
                else functions_str
            )
        except json.JSONDecodeError:
            functions = []

        # Convert expected output to valid_outputs list
        valid_outputs = self._normalize_expected_output(instance.expected_output)

        return StandardizedInstance(
            instance_id=instance.instance_id,
            input=user_query,
            context={
                "functions": functions,
                "task_type": "function_calling",
            },
            valid_outputs=valid_outputs,
            evaluation_type=EvaluationType.AST,
            metadata={
                "task_id": task.task_id,
                "category": instance.metadata.get("category", ""),
                "source": "bfcl",
            },
        )

    def _normalize_expected_output(self, expected_output: Any) -> list[Any]:
        """Normalize BFCL expected output to list of valid outputs.

        BFCL ground truth can be:
        - List of function call strings: ["func_name(arg=value)"]
        - Dict with function calls: {"func_name": {"arg": ["valid_value1", "valid_value2"]}}
        - Empty/None for irrelevance tests
        """
        if not expected_output:
            return []

        if isinstance(expected_output, list):
            return expected_output

        if isinstance(expected_output, dict):
            # Convert dict format to list of possible function calls
            return [expected_output]

        if isinstance(expected_output, str):
            return [expected_output]

        return [expected_output]


class AgentBenchTransformer(DatasetTransformer):
    """Transformer for AgentBench multi-turn agent tasks."""

    name = "agentbench"

    def transform(self, dataset: Dataset) -> StandardizedDataset:
        """Transform AgentBench dataset."""
        tasks = []

        for task in dataset.tasks:
            instances = [
                self.transform_instance(inst, task) for inst in task.instances
            ]

            tasks.append(
                StandardizedTask(
                    task_id=task.task_id,
                    name=task.name,
                    description=task.description,
                    category=task.category.value,
                    difficulty=task.difficulty.value,
                    instances=instances,
                    default_evaluation=EvaluationType.CUSTOM,
                    tags=task.tags,
                    source="agentbench",
                )
            )

        return StandardizedDataset(
            name=dataset.name,
            description=dataset.description,
            version=dataset.version,
            tasks=tasks,
            metadata=dataset.metadata,
        )

    def transform_instance(
        self, instance: TaskInstance, task: Task
    ) -> StandardizedInstance:
        """Transform AgentBench instance with environment context."""
        input_data = instance.input_data
        instruction = input_data.get("instruction", "")

        return StandardizedInstance(
            instance_id=instance.instance_id,
            input=instruction,
            context={
                "environment": input_data.get("environment", ""),
                "init_state": input_data.get("init_state", {}),
                "task_type": "agent",
            },
            valid_outputs=[instance.expected_output] if instance.expected_output else [],
            evaluation_type=EvaluationType.CUSTOM,
            metadata={
                "task_id": task.task_id,
                "turns": instance.metadata.get("turns", []),
                "requires_docker": instance.metadata.get("requires_docker", False),
                "source": "agentbench",
            },
        )


class DocILETransformer(DatasetTransformer):
    """Transformer for DocILE document extraction tasks."""

    name = "docile"

    def transform(self, dataset: Dataset) -> StandardizedDataset:
        """Transform DocILE dataset."""
        tasks = []

        for task in dataset.tasks:
            instances = [
                self.transform_instance(inst, task) for inst in task.instances
            ]

            tasks.append(
                StandardizedTask(
                    task_id=task.task_id,
                    name=task.name,
                    description=task.description,
                    category=task.category.value,
                    difficulty=task.difficulty.value,
                    instances=instances,
                    default_evaluation=EvaluationType.SCHEMA,
                    tags=task.tags,
                    source="docile",
                )
            )

        return StandardizedDataset(
            name=dataset.name,
            description=dataset.description,
            version=dataset.version,
            tasks=tasks,
            metadata=dataset.metadata,
        )

    def transform_instance(
        self, instance: TaskInstance, task: Task
    ) -> StandardizedInstance:
        """Transform DocILE instance."""
        input_data = instance.input_data

        return StandardizedInstance(
            instance_id=instance.instance_id,
            input=input_data.get("document_text", ""),
            context={
                "document_path": input_data.get("document_path", ""),
                "task_type": input_data.get("task_type", "kile"),
            },
            valid_outputs=[instance.expected_output] if instance.expected_output else [],
            evaluation_type=EvaluationType.SCHEMA,
            metadata={
                "task_id": task.task_id,
                "has_pdf": instance.metadata.get("has_pdf", False),
                "has_ocr": instance.metadata.get("has_ocr", False),
                "source": "docile",
            },
        )


# Transformer registry
_TRANSFORMER_REGISTRY: dict[str, type[DatasetTransformer]] = {
    "xy_benchmark": XYBenchmarkTransformer,
    "bfcl": BFCLTransformer,
    "agentbench": AgentBenchTransformer,
    "docile": DocILETransformer,
}


def get_transformer(name: str) -> DatasetTransformer:
    """Get a transformer by name.

    Args:
        name: Transformer name (matches dataset source)

    Returns:
        Instantiated transformer

    Raises:
        ValueError: If transformer not found
    """
    if name not in _TRANSFORMER_REGISTRY:
        available = list(_TRANSFORMER_REGISTRY.keys())
        raise ValueError(f"Unknown transformer: {name}. Available: {available}")
    return _TRANSFORMER_REGISTRY[name]()


def transform_dataset(dataset: Dataset) -> StandardizedDataset:
    """Auto-detect and transform a dataset to standardized format.

    Args:
        dataset: Dataset in native format

    Returns:
        StandardizedDataset
    """
    # Try to detect source from tasks
    source = "xy_benchmark"
    if dataset.tasks:
        first_source = dataset.tasks[0].source
        if first_source in _TRANSFORMER_REGISTRY:
            source = first_source
        elif "bfcl" in first_source.lower():
            source = "bfcl"
        elif "agentbench" in first_source.lower():
            source = "agentbench"
        elif "docile" in first_source.lower():
            source = "docile"

    transformer = get_transformer(source)
    return transformer.transform(dataset)


def list_transformers() -> list[str]:
    """List available dataset transformers."""
    return list(_TRANSFORMER_REGISTRY.keys())
