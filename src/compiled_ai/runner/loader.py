"""Dataset loaders for various benchmark formats."""

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from .dataset import Dataset, Task, TaskCategory, TaskDifficulty, TaskInstance


class DatasetAdapter(ABC):
    """Base adapter for converting external datasets."""

    name: str = "base"

    @abstractmethod
    def load(self, path: Path, **kwargs: Any) -> Dataset:
        """Load and convert external dataset to our format.

        Args:
            path: Path to the dataset
            **kwargs: Additional arguments for the adapter

        Returns:
            Dataset in our format
        """
        ...

    @abstractmethod
    def is_compatible(self, path: Path) -> bool:
        """Check if this adapter can handle the given path.

        Args:
            path: Path to check

        Returns:
            True if this adapter can load the dataset
        """
        ...


class BFCLAdapter(DatasetAdapter):
    """Adapter for Berkeley Function Calling Leaderboard v4.

    BFCL v4 focuses on function calling accuracy:
    - 2000+ test cases
    - Multiple categories: simple, parallel, multiple, irrelevance
    - AST-based evaluation

    High relevance: Tests deterministic function parameter extraction.
    """

    name = "bfcl"

    def load(self, path: Path, **kwargs: Any) -> Dataset:
        """Load BFCL v4 dataset.

        Args:
            path: Path to BFCL dataset directory
            **kwargs: Additional arguments

        Returns:
            Dataset with function calling tasks
        """
        dataset = Dataset(
            name="BFCL v4",
            description="Berkeley Function Calling Leaderboard v4",
            version="4.0",
        )

        # BFCL uses JSONL format with specific structure
        for jsonl_file in path.glob("*.jsonl"):
            category = jsonl_file.stem  # e.g., "simple", "parallel"

            instances = []
            with open(jsonl_file) as f:
                for i, line in enumerate(f):
                    data = json.loads(line)
                    instances.append(
                        TaskInstance(
                            instance_id=data.get("id", f"{category}_{i}"),
                            input_data={
                                "user_query": data.get("user_query", ""),
                                "functions": data.get("function", []),
                            },
                            expected_output=data.get("ground_truth", {}),
                            metadata={"category": category},
                        )
                    )

            if instances:
                task = Task(
                    task_id=f"bfcl_{category}",
                    name=f"BFCL {category.title()} Function Calling",
                    description=f"Function calling test: {category}",
                    category=TaskCategory.FUNCTION_CALLING,
                    difficulty=self._map_difficulty(category),
                    prompt_template=(
                        "Given these functions:\n{functions}\n\n"
                        "User query: {user_query}\n\n"
                        "Generate the appropriate function call(s)."
                    ),
                    instances=instances,
                    evaluation_type="ast_match",
                    tags=["function_calling", "bfcl", category],
                    source="bfcl_v4",
                )
                dataset.tasks.append(task)

        return dataset

    def _map_difficulty(self, category: str) -> TaskDifficulty:
        """Map BFCL category to difficulty.

        Args:
            category: BFCL category name

        Returns:
            Corresponding difficulty level
        """
        mapping = {
            "simple": TaskDifficulty.SIMPLE,
            "parallel": TaskDifficulty.MEDIUM,
            "multiple": TaskDifficulty.MEDIUM,
            "parallel_multiple": TaskDifficulty.COMPLEX,
            "irrelevance": TaskDifficulty.COMPLEX,
        }
        return mapping.get(category, TaskDifficulty.MEDIUM)

    def is_compatible(self, path: Path) -> bool:
        """Check for BFCL-style JSONL files."""
        return any(path.glob("*.jsonl")) and (path / "README.md").exists()


class DocILEAdapter(DatasetAdapter):
    """Adapter for DocILE document extraction benchmark.

    DocILE focuses on document information extraction:
    - Key-value extraction from documents
    - Table extraction
    - Entity recognition

    High relevance: Tests structured data extraction (EOB, invoices).
    """

    name = "docile"

    def load(self, path: Path, **kwargs: Any) -> Dataset:
        """Load DocILE dataset.

        Args:
            path: Path to DocILE dataset directory
            **kwargs: Additional arguments

        Returns:
            Dataset with document extraction tasks
        """
        dataset = Dataset(
            name="DocILE",
            description="Document Information Localization and Extraction",
            version="1.0",
        )

        # DocILE typically has annotations in JSON format
        annotations_file = path / "annotations.json"
        if not annotations_file.exists():
            annotations_file = path / "test.json"

        if annotations_file.exists():
            with open(annotations_file) as f:
                data = json.load(f)

            instances = []
            items = data.get("documents", data) if isinstance(data, dict) else data
            for i, item in enumerate(items):
                instances.append(
                    TaskInstance(
                        instance_id=item.get("id", f"doc_{i}"),
                        input_data={
                            "document_text": item.get("text", ""),
                            "document_path": item.get("path", ""),
                        },
                        expected_output=item.get(
                            "annotations", item.get("fields", {})
                        ),
                        metadata=item.get("metadata", {}),
                    )
                )

            if instances:
                task = Task(
                    task_id="docile_extraction",
                    name="DocILE Information Extraction",
                    description="Extract structured fields from documents",
                    category=TaskCategory.DOCUMENT_PROCESSING,
                    difficulty=TaskDifficulty.MEDIUM,
                    prompt_template=(
                        "Extract the following fields from this document:\n"
                        "{document_text}\n\n"
                        "Return as JSON with field names as keys."
                    ),
                    instances=instances,
                    evaluation_type="schema",
                    tags=["document", "extraction", "docile"],
                    source="docile",
                )
                dataset.tasks.append(task)

        return dataset

    def is_compatible(self, path: Path) -> bool:
        """Check for DocILE annotation files."""
        return (path / "annotations.json").exists() or (path / "test.json").exists()


class AgentBenchAdapter(DatasetAdapter):
    """Adapter for AgentBench multi-turn agent benchmark.

    AgentBench evaluates agent capabilities across environments:
    - Operating system tasks
    - Database operations
    - Web browsing
    - Knowledge graph queries

    Medium relevance: Tests multi-step task completion.
    """

    name = "agentbench"

    def load(self, path: Path, **kwargs: Any) -> Dataset:
        """Load AgentBench dataset.

        Args:
            path: Path to AgentBench dataset directory
            **kwargs: Additional arguments

        Returns:
            Dataset with multi-turn agent tasks
        """
        dataset = Dataset(
            name="AgentBench",
            description="Multi-turn agent benchmark",
            version="1.0",
        )

        # AgentBench has separate directories per environment
        for env_dir in path.iterdir():
            if env_dir.is_dir() and (env_dir / "tasks.json").exists():
                with open(env_dir / "tasks.json") as f:
                    tasks_data = json.load(f)

                instances = []
                for i, task_data in enumerate(tasks_data):
                    instances.append(
                        TaskInstance(
                            instance_id=task_data.get("id", f"{env_dir.name}_{i}"),
                            input_data={
                                "instruction": task_data.get("instruction", ""),
                                "environment": env_dir.name,
                            },
                            expected_output=task_data.get("expected_result", ""),
                            metadata={"turns": task_data.get("turns", [])},
                        )
                    )

                if instances:
                    task = Task(
                        task_id=f"agentbench_{env_dir.name}",
                        name=f"AgentBench {env_dir.name.title()}",
                        description=f"Agent tasks in {env_dir.name} environment",
                        category=TaskCategory.API_ORCHESTRATION,
                        difficulty=TaskDifficulty.COMPLEX,
                        prompt_template="Environment: {environment}\n\nTask: {instruction}",
                        instances=instances,
                        evaluation_type="milestone",
                        tags=["agent", "multi_turn", env_dir.name],
                        source="agentbench",
                    )
                    dataset.tasks.append(task)

        return dataset

    def is_compatible(self, path: Path) -> bool:
        """Check for AgentBench environment directories."""
        return any(
            (p / "tasks.json").exists() for p in path.iterdir() if p.is_dir()
        )


# Adapter registry
_ADAPTER_REGISTRY: dict[str, type[DatasetAdapter]] = {
    "bfcl": BFCLAdapter,
    "docile": DocILEAdapter,
    "agentbench": AgentBenchAdapter,
}


def register_adapter(name: str):
    """Decorator to register a dataset adapter.

    Args:
        name: Unique name for the adapter

    Returns:
        Decorator that registers the adapter class
    """

    def decorator(cls: type[DatasetAdapter]) -> type[DatasetAdapter]:
        _ADAPTER_REGISTRY[name] = cls
        cls.name = name
        return cls

    return decorator


class DatasetLoader:
    """Unified loader for all dataset formats."""

    def __init__(self, datasets_dir: Path | str = "datasets") -> None:
        """Initialize the dataset loader.

        Args:
            datasets_dir: Base directory for datasets
        """
        self.datasets_dir = Path(datasets_dir)

    def load(self, name: str, **kwargs: Any) -> Dataset:
        """Load a dataset by name.

        Args:
            name: Dataset name (e.g., "xy_benchmark", "bfcl")
            **kwargs: Additional arguments for the adapter

        Returns:
            Loaded Dataset object

        Raises:
            ValueError: If dataset not found or no compatible adapter
        """
        path = self.datasets_dir / name

        if not path.exists():
            raise ValueError(f"Dataset not found: {path}")

        # Check for XY_Benchmark format (has metadata.yaml)
        if (path / "metadata.yaml").exists() or (path / "metadata.json").exists():
            return Dataset.from_directory(path)

        # Try adapters for external formats
        for adapter_cls in _ADAPTER_REGISTRY.values():
            adapter = adapter_cls()
            if adapter.is_compatible(path):
                return adapter.load(path, **kwargs)

        raise ValueError(f"No compatible adapter found for: {path}")

    def load_external(
        self, adapter_name: str, path: Path | str, **kwargs: Any
    ) -> Dataset:
        """Load an external dataset with a specific adapter.

        Args:
            adapter_name: Name of the adapter to use
            path: Path to the dataset
            **kwargs: Additional arguments for the adapter

        Returns:
            Loaded Dataset object

        Raises:
            ValueError: If adapter not found
        """
        if adapter_name not in _ADAPTER_REGISTRY:
            available = list(_ADAPTER_REGISTRY.keys())
            raise ValueError(
                f"Unknown adapter: {adapter_name}. Available: {available}"
            )

        adapter = _ADAPTER_REGISTRY[adapter_name]()
        return adapter.load(Path(path), **kwargs)

    def list_datasets(self) -> list[str]:
        """List available datasets in the datasets directory.

        Returns:
            List of dataset names
        """
        if not self.datasets_dir.exists():
            return []
        return [p.name for p in self.datasets_dir.iterdir() if p.is_dir()]

    def list_adapters(self) -> list[str]:
        """List available dataset adapters.

        Returns:
            List of adapter names
        """
        return list(_ADAPTER_REGISTRY.keys())
