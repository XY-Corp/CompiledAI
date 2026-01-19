# XY Local Workflow Executor

A lightweight, standalone executor for running DSL workflows locally without Temporal or database dependencies. Designed for benchmarking, testing, and development.

## Features

- Execute YAML-based DSL workflows locally
- No Temporal or database dependencies
- Activity mocking with various patterns (instant, delayed, fail, file-based)
- Built-in benchmarking and timing collection
- CLI and Python API interfaces
- Support for sequence, parallel, and forEach execution patterns
- Template resolution with `${{ variable }}` syntax

## Installation

```bash
cd XYLocalWorkflowExecutor

# Using uv (recommended)
uv sync

# Or install in editable mode
uv pip install -e .

# Or with pip
pip install -e .
```

## Quick Start

### CLI Usage

```bash
# Run a workflow
xy-workflow examples/sample_workflow.yaml

# Override input variables
xy-workflow workflow.yaml \
    --var 'customers=["CUSTOMER_A", "CUSTOMER_B"]' \
    --var skip_processing=true

# Dry run (validate only)
xy-workflow workflow.yaml --dry-run

# Verbose output with benchmarks
xy-workflow workflow.yaml --verbose --benchmark

# Mock activities
xy-workflow workflow.yaml \
    --mock fetch_data=instant \
    --mock slow_api=delay:2000 \
    --mock external_service=file:mock_response.json
```

### Mock Specifications

| Spec | Description |
|------|-------------|
| `instant` | Return success immediately |
| `delay:1000` | Delay 1000ms then return success |
| `fail:error message` | Fail with specified error |
| `file:path.json` | Load response from JSON file |

### Python API

```python
import asyncio
from xy_local_executor import LocalWorkflowExecutor, ActivityMocks, create_mock_registry

# Simple usage with predefined mocks
async def run_workflow():
    executor = LocalWorkflowExecutor(
        mock_activities={
            "my_activity": ActivityMocks.instant_success,
            "slow_activity": ActivityMocks.delayed(1000),
            "failing_activity": ActivityMocks.failing("Expected error"),
        },
        verbose=True,
    )

    result = await executor.run_yaml(
        "workflow.yaml",
        variables={"input_param": "value"},
    )
    return result

asyncio.run(run_workflow())
```

### Using Mock Registry Helper

```python
from xy_local_executor import create_mock_registry

# Create mocks using the helper
mocks = create_mock_registry(
    instant=["init_activity", "cleanup_activity"],
    delayed={"slow_api": 2000, "medium_api": 500},
    failing={"broken_activity": "Service unavailable"},
)

# Add custom implementations
async def custom_activity(param1: str, **kwargs) -> dict:
    return {"result": f"Processed {param1}"}

mocks["custom_activity"] = custom_activity
```

### Custom Activity Mocks

```python
async def my_custom_mock(
    org_id: str,
    user_id: str,
    workflow_definition_id: str,
    workflow_instance_id: str,
    **params,
) -> dict:
    """Custom mock with full context access."""
    return {
        "status": "success",
        "processed_by": org_id,
        "custom_data": params.get("input_data"),
    }

executor = LocalWorkflowExecutor(
    mock_activities={"my_activity": my_custom_mock},
)
```

## Workflow YAML Structure

```yaml
workflow_id: my-workflow
name: My Workflow
description: Example workflow

# Input variables
variables:
  items:
    - item1
    - item2
  max_retries: 3

# Root statement
root:
  sequence:
    elements:
      # Simple activity
      - activity:
          name: initialize
          params:
            config: ${{ variables.config }}
          result: init_result

      # Parallel execution
      - parallel:
          branches:
            - activity:
                name: task_a
                result: result_a
            - activity:
                name: task_b
                result: result_b

      # ForEach with concurrency control
      - foreach:
          items: items
          item_variable: current_item
          max_concurrent: 5
          statement:
            activity:
              name: process_item
              params:
                item: ${{ current_item }}
              result: item_result
```

## Benchmarking

The executor includes built-in benchmarking capabilities:

```python
from xy_local_executor import LocalWorkflowExecutor, BenchmarkCollector

executor = LocalWorkflowExecutor(
    mock_activities=mocks,
    verbose=True,
)

result = await executor.run_yaml("workflow.yaml")

# Access benchmark data (if executor exposes it)
# Benchmarks track:
# - Activity execution times
# - Start/end timestamps
# - Success/failure counts
```

## Package Structure

```
XYLocalWorkflowExecutor/
├── pyproject.toml           # Package configuration
├── README.md                # This file
├── src/
│   └── xy_local_executor/
│       ├── __init__.py      # Package exports
│       ├── executor.py      # LocalWorkflowExecutor
│       ├── benchmarking.py  # Timing utilities
│       ├── mocks.py         # Activity mocking
│       ├── cli.py           # CLI interface
│       └── dsl/
│           ├── models.py    # Pydantic DSL models
│           ├── parser.py    # YAML parser
│           ├── template.py  # Template resolution
│           └── execution.py # Execution utilities
├── examples/
│   └── sample_workflow.yaml # Example workflow
├── scripts/
│   └── run_workflow.py      # Example runner
└── tests/
    └── ...                  # Test files
```

## Dependencies

Minimal dependencies for lightweight execution:

- `pydantic>=2.0` - Data validation and models
- `pyyaml>=6.0` - YAML parsing

## Development

```bash
# Install with dev dependencies
uv sync --all-extras

# Run tests
pytest

# Run tests with coverage
pytest --cov=xy_local_executor
```

## Design Decisions

1. **No database**: All state is in-memory, activities must be mocked
2. **No default registry**: Explicit mocks required (prevents accidental real calls)
3. **Standalone DSL**: Self-contained DSL models (no platform imports)
4. **Minimal dependencies**: Only pydantic + pyyaml
5. **Same execution semantics**: ForEach, Parallel, Sequence work identically to Temporal version

## License

Internal use only - XY Platform
