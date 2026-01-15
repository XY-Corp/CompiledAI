"""Dataset models for benchmark tasks."""

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import yaml


class TaskCategory(str, Enum):
    """Task categories matching framework.md."""

    DOCUMENT_PROCESSING = "document_processing"
    DATA_TRANSFORMATION = "data_transformation"
    DECISION_LOGIC = "decision_logic"
    API_ORCHESTRATION = "api_orchestration"
    FUNCTION_CALLING = "function_calling"
    CODE_GENERATION = "code_generation"


class TaskDifficulty(str, Enum):
    """Task difficulty levels."""

    SIMPLE = "simple"
    MEDIUM = "medium"
    COMPLEX = "complex"


@dataclass
class TaskInstance:
    """A single test instance within a task."""

    instance_id: str
    input_data: dict[str, Any]
    expected_output: Any
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Task:
    """A benchmark task with multiple test instances."""

    task_id: str
    name: str
    description: str
    category: TaskCategory
    difficulty: TaskDifficulty

    # Task specification
    prompt_template: str
    system_prompt: str | None = None

    # Test instances
    instances: list[TaskInstance] = field(default_factory=list)

    # Evaluation config
    evaluation_type: str = "exact_match"  # exact_match, semantic, schema, custom
    schema: dict[str, Any] | None = None  # JSON schema for output validation

    # Metadata
    tags: list[str] = field(default_factory=list)
    source: str = "xy_benchmark"
    version: str = "1.0"


@dataclass
class Dataset:
    """A collection of benchmark tasks."""

    name: str
    description: str
    version: str
    tasks: list[Task] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_directory(cls, path: Path) -> "Dataset":
        """Load dataset from a directory structure.

        Args:
            path: Path to dataset directory containing metadata.yaml and tasks/

        Returns:
            Dataset loaded from the directory
        """
        metadata_file = path / "metadata.yaml"
        if not metadata_file.exists():
            metadata_file = path / "metadata.json"

        if metadata_file.suffix == ".yaml":
            with open(metadata_file) as f:
                metadata = yaml.safe_load(f)
        else:
            with open(metadata_file) as f:
                metadata = json.load(f)

        dataset = cls(
            name=metadata.get("name", path.name),
            description=metadata.get("description", ""),
            version=metadata.get("version", "1.0"),
            metadata=metadata,
        )

        # Load tasks from tasks/ subdirectory
        tasks_dir = path / "tasks"
        if tasks_dir.exists():
            for task_file in sorted(tasks_dir.glob("*.json")):
                task = cls._load_task(task_file)
                dataset.tasks.append(task)
            for task_file in sorted(tasks_dir.glob("*.yaml")):
                task = cls._load_task(task_file)
                dataset.tasks.append(task)

        return dataset

    @staticmethod
    def _load_task(path: Path) -> Task:
        """Load a single task from file.

        Args:
            path: Path to task file (JSON or YAML)

        Returns:
            Task loaded from file
        """
        if path.suffix == ".yaml":
            with open(path) as f:
                data = yaml.safe_load(f)
        else:
            with open(path) as f:
                data = json.load(f)

        instances = [
            TaskInstance(
                instance_id=inst.get("id", f"inst_{i}"),
                input_data=inst.get("input", {}),
                expected_output=inst.get("expected_output"),
                metadata=inst.get("metadata", {}),
            )
            for i, inst in enumerate(data.get("instances", []))
        ]

        return Task(
            task_id=data.get("id", path.stem),
            name=data.get("name", path.stem),
            description=data.get("description", ""),
            category=TaskCategory(data.get("category", "document_processing")),
            difficulty=TaskDifficulty(data.get("difficulty", "simple")),
            prompt_template=data.get("prompt_template", ""),
            system_prompt=data.get("system_prompt"),
            instances=instances,
            evaluation_type=data.get("evaluation_type", "exact_match"),
            schema=data.get("schema"),
            tags=data.get("tags", []),
            source=data.get("source", "xy_benchmark"),
            version=data.get("version", "1.0"),
        )

    def filter_by_category(self, category: TaskCategory) -> list[Task]:
        """Filter tasks by category.

        Args:
            category: Category to filter by

        Returns:
            List of tasks matching the category
        """
        return [t for t in self.tasks if t.category == category]

    def filter_by_difficulty(self, difficulty: TaskDifficulty) -> list[Task]:
        """Filter tasks by difficulty.

        Args:
            difficulty: Difficulty level to filter by

        Returns:
            List of tasks matching the difficulty
        """
        return [t for t in self.tasks if t.difficulty == difficulty]

    def filter_by_tags(self, tags: list[str]) -> list[Task]:
        """Filter tasks by tags (any match).

        Args:
            tags: List of tags to match

        Returns:
            List of tasks with any of the specified tags
        """
        return [t for t in self.tasks if any(tag in t.tags for tag in tags)]
