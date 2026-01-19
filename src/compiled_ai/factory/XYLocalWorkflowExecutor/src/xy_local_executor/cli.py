#!/usr/bin/env python3
"""CLI for running DSL workflows locally.

Usage:
    # Basic execution
    xy-workflow workflow.yaml

    # With variable overrides
    xy-workflow workflow.yaml --var customers='["ARKVIEW"]'

    # Dry run (parse and validate only)
    xy-workflow workflow.yaml --dry-run

    # Verbose output with benchmarking
    xy-workflow workflow.yaml --verbose --benchmark

    # Mock specific activities
    xy-workflow workflow.yaml --mock wait_for_task=instant
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict


def parse_var(var_str: str) -> tuple[str, Any]:
    """Parse a --var KEY=VALUE argument."""
    if '=' not in var_str:
        raise argparse.ArgumentTypeError(
            f"Invalid variable format: '{var_str}'. Expected KEY=VALUE"
        )

    key, value = var_str.split('=', 1)
    key = key.strip()

    # Try to parse as JSON (for lists, dicts, bools, numbers)
    try:
        parsed_value = json.loads(value)
    except json.JSONDecodeError:
        # Keep as string if not valid JSON
        parsed_value = value

    return key, parsed_value


def create_mock_activity(mock_spec: str):
    """
    Create a mock activity from a specification string.

    Supported formats:
        - "instant" - Instant success
        - "delay:1000" - Delay 1000ms then success
        - "fail:error message" - Fail with error
        - "file:path/to/response.json" - Load response from file
    """

    if mock_spec == "instant" or not mock_spec:
        async def instant_mock(**kwargs):
            return {"status": "success", "operation_status": "success", "mocked": True}
        return instant_mock

    if mock_spec.startswith("delay:"):
        delay_ms = int(mock_spec.split(":", 1)[1])
        async def delay_mock(**kwargs):
            await asyncio.sleep(delay_ms / 1000)
            return {"status": "success", "operation_status": "success", "mocked": True}
        return delay_mock

    if mock_spec.startswith("fail:"):
        error_msg = mock_spec.split(":", 1)[1]
        async def fail_mock(**kwargs):
            raise RuntimeError(error_msg)
        return fail_mock

    if mock_spec.startswith("file:"):
        file_path = Path(mock_spec.split(":", 1)[1])
        async def file_mock(**kwargs):
            with open(file_path, 'r') as f:
                return json.load(f)
        return file_mock

    # Default: treat as instant success
    async def default_mock(**kwargs):
        return {"status": "success", "operation_status": "success", "mocked": True}
    return default_mock


def main():
    parser = argparse.ArgumentParser(
        description='Run DSL workflows locally without Temporal',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run a workflow
  xy-workflow workflow.yaml

  # Override input variables
  xy-workflow workflow.yaml \\
    --var 'customers=["ARKVIEW"]' \\
    --var skip_rl=true

  # Dry run (validate only)
  xy-workflow workflow.yaml --dry-run

  # Verbose with benchmarks
  xy-workflow workflow.yaml --verbose --benchmark

  # Mock activities
  xy-workflow workflow.yaml \\
    --mock wait_for_task=instant \\
    --mock fetch_data=file:mock_response.json

Mock Specifications:
  instant              - Return success immediately
  delay:1000           - Delay 1000ms then return success
  fail:error message   - Fail with specified error
  file:path.json       - Load response from JSON file
"""
    )

    parser.add_argument(
        'workflow',
        type=Path,
        help='Path to YAML workflow file'
    )

    parser.add_argument(
        '--var', '-v',
        action='append',
        dest='variables',
        metavar='KEY=VALUE',
        help='Override input variable (can be repeated)'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Parse and validate without executing'
    )

    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable detailed logging'
    )

    parser.add_argument(
        '--benchmark',
        action='store_true',
        help='Show timing breakdown per activity'
    )

    parser.add_argument(
        '--mock', '-m',
        action='append',
        dest='mocks',
        metavar='ACTIVITY=SPEC',
        help='Mock an activity (can be repeated). SPEC: instant, delay:ms, fail:msg, file:path'
    )

    parser.add_argument(
        '--workflow-id',
        help='Override workflow ID'
    )

    parser.add_argument(
        '--org-id',
        help='Override organization ID'
    )

    parser.add_argument(
        '--user-id',
        help='Override user ID'
    )

    parser.add_argument(
        '--output', '-o',
        type=Path,
        metavar='FILE',
        help='Save results to JSON file'
    )

    parser.add_argument(
        '--use-builtins',
        action='store_true',
        help='Use built-in activities (file operations, data transforms, etc.)'
    )

    args = parser.parse_args()

    # Resolve workflow path
    workflow_path = args.workflow
    if not workflow_path.is_absolute():
        workflow_path = Path.cwd() / workflow_path

    if not workflow_path.exists():
        print(f"Error: Workflow file not found: {workflow_path}", file=sys.stderr)
        sys.exit(1)

    # Parse variable overrides
    variables: Dict[str, Any] = {}
    if args.variables:
        for var_str in args.variables:
            try:
                key, value = parse_var(var_str)
                variables[key] = value
            except argparse.ArgumentTypeError as e:
                print(f"Error: {e}", file=sys.stderr)
                sys.exit(1)

    # Parse mock specifications
    mock_activities: Dict[str, Any] = {}
    if args.mocks:
        for mock_str in args.mocks:
            if '=' in mock_str:
                name, spec = mock_str.split('=', 1)
            else:
                name, spec = mock_str, "instant"
            mock_activities[name] = create_mock_activity(spec)

    # Run the workflow
    async def run_workflow():
        # Import here to avoid circular imports and allow --help without full import
        from xy_local_executor.executor import LocalWorkflowExecutor

        # Build activity registry
        activities = dict(mock_activities) if mock_activities else {}

        # Add built-in activities if requested
        if args.use_builtins:
            from xy_local_executor.activities import BUILTIN_ACTIVITIES
            # Built-ins can be overridden by mocks
            activities = {**BUILTIN_ACTIVITIES, **activities}

        executor = LocalWorkflowExecutor(
            mock_activities=activities if activities else None,
            dry_run=args.dry_run,
            verbose=args.verbose,
            org_id=args.org_id,
            user_id=args.user_id,
        )

        print("=" * 70)
        print("XY LOCAL WORKFLOW EXECUTOR")
        print("=" * 70)
        print(f"Workflow: {workflow_path}")
        print(f"Dry Run:  {args.dry_run}")
        print(f"Verbose:  {args.verbose}")
        if variables:
            print(f"Variables: {json.dumps(variables, default=str)}")
        if mock_activities:
            print(f"Mocks:    {list(mock_activities.keys())}")
        print("=" * 70)
        print()

        result = await executor.run_yaml(
            workflow_path,
            variables=variables,
            config_flow_id=args.workflow_id,
        )

        print()
        print("=" * 70)
        print("WORKFLOW COMPLETED")
        print("=" * 70)

        # Show final variables
        print("\nFinal Variables:")
        for key, value in result.items():
            value_str = json.dumps(value, default=str) if isinstance(value, (dict, list)) else str(value)
            if len(value_str) > 100:
                value_str = value_str[:100] + "..."
            print(f"  {key}: {value_str}")

        # Save to JSON file if requested
        if args.output:
            output_path = args.output
            if not output_path.is_absolute():
                output_path = Path.cwd() / output_path
            with open(output_path, 'w') as f:
                json.dump(result, f, indent=2, default=str)
            print(f"\nResults saved to: {output_path}")

        # Show benchmark report if requested
        if args.benchmark:
            print()
            # Note: Would need to access ctx.benchmarks to show report
            # This would require modifying the executor to return benchmarks

        return result

    try:
        asyncio.run(run_workflow())
    except KeyboardInterrupt:
        print("\n\nWorkflow interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
