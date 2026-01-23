"""Benchmark Runner: Orchestrates benchmark execution and result collection."""

from .benchmark import (
    BenchmarkConfig,
    BenchmarkResult,
    BenchmarkRunner,
    InstanceLog,
    TaskResult,
)
from .dataset import Dataset, Task, TaskCategory, TaskDifficulty, TaskInstance
from .loader import (
    AgentBenchAdapter,
    BFCLAdapter,
    DatasetAdapter,
    DatasetLoader,
    DocILEAdapter,
    register_adapter,
)
from .standardized import (
    EvaluationType,
    StandardizedDataset,
    StandardizedInstance,
    StandardizedTask,
)
from .transformers import (
    AgentBenchTransformer,
    BFCLTransformer,
    DatasetTransformer,
    DocILETransformer,
    XYBenchmarkTransformer,
    get_transformer,
    list_transformers,
    transform_dataset,
)
# NOTE: bfcl_helpers removed - use compiled_ai.datasets.BFCLConverter instead

__all__ = [
    # Dataset
    "Dataset",
    "Task",
    "TaskInstance",
    "TaskCategory",
    "TaskDifficulty",
    # Standardized format
    "StandardizedDataset",
    "StandardizedTask",
    "StandardizedInstance",
    "EvaluationType",
    # Transformers
    "DatasetTransformer",
    "XYBenchmarkTransformer",
    "BFCLTransformer",
    "AgentBenchTransformer",
    "DocILETransformer",
    "get_transformer",
    "list_transformers",
    "transform_dataset",
    # Loader
    "DatasetLoader",
    "DatasetAdapter",
    "BFCLAdapter",
    "DocILEAdapter",
    "AgentBenchAdapter",
    "register_adapter",
    # Runner
    "BenchmarkRunner",
    "BenchmarkConfig",
    "BenchmarkResult",
    "TaskResult",
    "InstanceLog",
]
