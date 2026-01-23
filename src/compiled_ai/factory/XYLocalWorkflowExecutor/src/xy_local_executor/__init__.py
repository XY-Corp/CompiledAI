"""XY Local Workflow Executor - Standalone DSL workflow execution without Temporal.

This package provides a lightweight executor for running DSL workflows locally,
designed for benchmarking and testing without database or Temporal dependencies.

Usage:
    from xy_local_executor import LocalWorkflowExecutor, ActivityMocks

    executor = LocalWorkflowExecutor(
        mock_activities={
            "my_activity": ActivityMocks.instant_success,
        },
        verbose=True,
    )

    result = await executor.run_yaml(
        "workflow.yaml",
        variables={"input_param": "value"},
    )
"""

from xy_local_executor.executor import LocalWorkflowExecutor, ExecutionContext
from xy_local_executor.benchmarking import (
    BenchmarkCollector,
    ActivityBenchmark,
    BenchmarkSummary,
)
from xy_local_executor.mocks import ActivityMocks, create_mock_registry
from xy_local_executor.activities import BUILTIN_ACTIVITIES

__version__ = "0.1.0"

__all__ = [
    # Core
    "LocalWorkflowExecutor",
    "ExecutionContext",
    # Benchmarking
    "BenchmarkCollector",
    "ActivityBenchmark",
    "BenchmarkSummary",
    # Mocking
    "ActivityMocks",
    "create_mock_registry",
    # Built-in activities
    "BUILTIN_ACTIVITIES",
]
