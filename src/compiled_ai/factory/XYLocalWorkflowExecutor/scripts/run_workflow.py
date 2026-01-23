#!/usr/bin/env python3
"""Example script showing how to use the LocalWorkflowExecutor programmatically.

Usage:
    python scripts/run_workflow.py
    python scripts/run_workflow.py --workflow examples/sample_workflow.yaml
    python scripts/run_workflow.py --verbose --benchmark
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from xy_local_executor import (
    LocalWorkflowExecutor,
    ActivityMocks,
    create_mock_registry,
)


def create_custom_mocks() -> dict:
    """Create custom mocks for the sample workflow activities."""

    async def fetch_customer_data(customer_id: str, **kwargs) -> dict:
        """Mock that returns simulated customer data."""
        return {
            "customer_id": customer_id,
            "name": f"Customer {customer_id}",
            "balance": 1000.00,
            "status": "active",
        }

    async def process_customer(customer_id: str, data: dict, **kwargs) -> dict:
        """Mock that simulates customer processing."""
        await asyncio.sleep(0.1)  # Simulate some work
        return {
            "customer_id": customer_id,
            "processed": True,
            "result": "success",
        }

    # Use the mock registry helper for common patterns
    mocks = create_mock_registry(
        instant=["initialize_workflow", "complete_workflow"],
        delayed={"generate_report": 200, "send_notifications": 100},
    )

    # Add custom implementations
    mocks["fetch_customer_data"] = fetch_customer_data
    mocks["process_customer"] = process_customer

    return mocks


async def run_example(
    workflow_path: Path,
    variables: dict | None = None,
    verbose: bool = False,
    benchmark: bool = False,
):
    """Run an example workflow with mocked activities."""

    # Create executor with mocks
    executor = LocalWorkflowExecutor(
        mock_activities=create_custom_mocks(),
        verbose=verbose,
        org_id="example-org",
        user_id="example-user",
    )

    print("=" * 70)
    print("XY LOCAL WORKFLOW EXECUTOR - Example Runner")
    print("=" * 70)
    print(f"Workflow: {workflow_path}")
    print(f"Verbose:  {verbose}")
    print(f"Benchmark: {benchmark}")
    if variables:
        print(f"Variables: {json.dumps(variables, default=str)}")
    print("=" * 70)
    print()

    # Run the workflow
    result = await executor.run_yaml(
        workflow_path,
        variables=variables or {},
    )

    print()
    print("=" * 70)
    print("WORKFLOW COMPLETED")
    print("=" * 70)

    # Show results
    print("\nFinal Variables:")
    for key, value in result.items():
        value_str = json.dumps(value, default=str) if isinstance(value, (dict, list)) else str(value)
        if len(value_str) > 100:
            value_str = value_str[:100] + "..."
        print(f"  {key}: {value_str}")

    return result


def main():
    parser = argparse.ArgumentParser(
        description='Run example workflow with LocalWorkflowExecutor'
    )

    parser.add_argument(
        '--workflow',
        type=Path,
        default=Path(__file__).parent.parent / 'examples' / 'sample_workflow.yaml',
        help='Path to workflow YAML file'
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )

    parser.add_argument(
        '--benchmark',
        action='store_true',
        help='Show benchmark timing'
    )

    args = parser.parse_args()

    try:
        asyncio.run(run_example(
            workflow_path=args.workflow,
            verbose=args.verbose,
            benchmark=args.benchmark,
        ))
    except KeyboardInterrupt:
        print("\nInterrupted by user")
    except Exception as e:
        print(f"\nError: {e}")
        raise


if __name__ == "__main__":
    main()
