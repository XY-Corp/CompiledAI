"""Local workflow executor for testing and benchmarking.

This module provides a LocalWorkflowExecutor that executes DSL workflows
locally without requiring Temporal infrastructure or database connections.

Usage:
    from xy_local_executor import LocalWorkflowExecutor, ActivityMocks

    executor = LocalWorkflowExecutor(
        mock_activities={
            "my_activity": ActivityMocks.instant_success,
        },
        verbose=True
    )
    result = await executor.run_yaml("path/to/workflow.yaml")
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import yaml

from xy_local_executor.dsl.models import (
    DSLInput,
    Statement,
    ActivityStatement,
    SequenceStatement,
    ParallelStatement,
    ForEachStatement,
    ChildWorkflowStatement,
)
from xy_local_executor.dsl.parser import build_dsl_input
from xy_local_executor.dsl.execution import (
    resolve_activity_params,
    resolve_foreach_items,
    create_iteration_vars,
    DSLExecutionError,
    TemplateResolutionError,
    DSLStructureError,
)


@dataclass
class ActivityBenchmark:
    """Benchmark data for a single activity execution."""
    name: str
    path: str  # DSL tree path
    start_time: datetime
    end_time: datetime
    duration_ms: float
    status: str  # "success", "error", "skipped"
    error: Optional[str] = None
    params: Optional[Dict[str, Any]] = None
    result: Optional[Dict[str, Any]] = None


@dataclass
class ExecutionContext:
    """Context for workflow execution."""
    workflow_definition_id: str
    workflow_instance_id: str
    metadata: Dict[str, Any]
    variables: Dict[str, Any]
    benchmarks: List[ActivityBenchmark] = field(default_factory=list)
    verbose: bool = False
    dry_run: bool = False


class LocalWorkflowExecutor:
    """
    Execute DSL workflows locally without Temporal.

    This executor runs workflows directly in-process, making it ideal for:
    - Testing workflow logic
    - Benchmarking activity performance
    - Debugging with breakpoints
    - CI/CD pipeline validation

    Args:
        activity_registry: Custom activity registry (dict of name -> callable)
        mock_activities: Dict of activity names to mock functions (overrides registry)
        dry_run: If True, parse and validate only (no execution)
        verbose: If True, enable detailed logging
        org_id: Default organization ID for activities
        user_id: Default user ID for activities

    Example:
        >>> from xy_local_executor import LocalWorkflowExecutor, ActivityMocks
        >>> executor = LocalWorkflowExecutor(
        ...     mock_activities={
        ...         "fetch_data": ActivityMocks.instant_success,
        ...         "process_item": ActivityMocks.delayed(100),
        ...     },
        ...     verbose=True
        ... )
        >>> result = await executor.run_yaml("workflow.yaml", variables={"count": 10})
    """

    def __init__(
        self,
        activity_registry: Optional[Dict[str, Callable]] = None,
        mock_activities: Optional[Dict[str, Callable]] = None,
        dry_run: bool = False,
        verbose: bool = False,
        org_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ):
        # Build activity lookup: base registry + mocks
        # Note: No default registry - all activities must be explicitly provided
        self.activities = dict(activity_registry or {})
        if mock_activities:
            self.activities.update(mock_activities)

        self.dry_run = dry_run
        self.verbose = verbose
        self.org_id = org_id or "default-org"
        self.user_id = user_id or "default-user"

    def _log(self, message: str, level: str = "INFO"):
        """Log a message if verbose mode is enabled."""
        if self.verbose:
            timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            print(f"{timestamp} [{level}] {message}")

    async def run_yaml(
        self,
        yaml_path: str | Path,
        variables: Optional[Dict[str, Any]] = None,
        config_flow_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute a workflow from a YAML file.

        Args:
            yaml_path: Path to the YAML workflow file
            variables: Override variables (merged with YAML defaults)
            config_flow_id: Override config_flow_id (defaults to generated UUID)

        Returns:
            Final workflow variables after execution
        """
        yaml_path = Path(yaml_path)
        if not yaml_path.exists():
            raise FileNotFoundError(f"Workflow YAML not found: {yaml_path}")

        with open(yaml_path, 'r') as f:
            yaml_content = f.read()

        # Build DSLInput using the standard parser
        dsl_input = build_dsl_input(
            config_flow_id=config_flow_id or f"local-{uuid.uuid4().hex[:8]}",
            execution_yaml=yaml_content,
            input_data=variables or {},
            metadata={
                "user_id": self.user_id,
                "organization_id": self.org_id,
            }
        )

        return await self.run(dsl_input)

    async def run(self, dsl_input: DSLInput) -> Dict[str, Any]:
        """
        Execute a DSLInput workflow.

        Args:
            dsl_input: Parsed DSLInput to execute

        Returns:
            Final workflow variables after execution
        """
        # Handle both old (config_flow_id) and new (workflow_definition_id/workflow_instance_id) DSLInput models
        if hasattr(dsl_input, 'workflow_definition_id') and dsl_input.workflow_definition_id:
            workflow_definition_id = dsl_input.workflow_definition_id
            workflow_instance_id = dsl_input.workflow_instance_id or workflow_definition_id
        else:
            # Use config_flow_id for both
            workflow_definition_id = dsl_input.config_flow_id or "local-workflow"
            workflow_instance_id = dsl_input.root_config_flow_id or dsl_input.config_flow_id or "local-workflow"

        # Create execution context
        ctx = ExecutionContext(
            workflow_definition_id=workflow_definition_id,
            workflow_instance_id=workflow_instance_id,
            metadata=dsl_input.metadata,
            variables=dict(dsl_input.variables),
            verbose=self.verbose,
            dry_run=self.dry_run,
        )

        self._log(f"Starting workflow: {ctx.workflow_instance_id}")
        self._log(f"Variables: {list(ctx.variables.keys())}")

        if self.dry_run:
            self._log("DRY RUN - Skipping execution")
            return ctx.variables

        try:
            # Execute the root statement
            await self._execute_statement(dsl_input.root, ctx, path="root")
            self._log(f"Workflow completed: {ctx.workflow_instance_id}")
        except Exception as e:
            self._log(f"Workflow failed: {e}", level="ERROR")
            raise

        return ctx.variables

    async def _execute_statement(
        self,
        stmt: Statement,
        ctx: ExecutionContext,
        path: str = "root",
        local_vars: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Execute a single DSL statement (recursive).

        Args:
            stmt: Statement to execute
            ctx: Execution context
            path: Structural path in DSL tree
            local_vars: Local variables (for forEach iterations)
        """
        # Use local vars if provided, otherwise use context variables
        active_vars = local_vars if local_vars is not None else ctx.variables

        if isinstance(stmt, ActivityStatement):
            await self._execute_activity(stmt, ctx, path, active_vars)

        elif isinstance(stmt, SequenceStatement):
            self._log(f"[{path}] Sequence: {len(stmt.sequence.elements)} elements")
            for i, elem in enumerate(stmt.sequence.elements):
                await self._execute_statement(elem, ctx, f"{path}.seq[{i}]", local_vars)

        elif isinstance(stmt, ParallelStatement):
            self._log(f"[{path}] Parallel: {len(stmt.parallel.branches)} branches")
            await asyncio.gather(*[
                self._execute_statement(branch, ctx, f"{path}.par[{i}]", local_vars)
                for i, branch in enumerate(stmt.parallel.branches)
            ])

        elif isinstance(stmt, ForEachStatement):
            await self._execute_foreach(stmt, ctx, path, active_vars)

        elif isinstance(stmt, ChildWorkflowStatement):
            # Execute child workflow in same process (no isolation)
            prefix = stmt.child_workflow.workflow_id_prefix or "child"
            child_path = f"{path}.child[{prefix}]"
            self._log(f"[{child_path}] Child workflow (inline)")
            await self._execute_statement(
                stmt.child_workflow.statement,
                ctx,
                child_path,
                local_vars
            )

        else:
            raise ValueError(f"Unknown statement type: {type(stmt)}")

    async def _execute_activity(
        self,
        stmt: ActivityStatement,
        ctx: ExecutionContext,
        path: str,
        active_vars: Dict[str, Any],
    ) -> None:
        """Execute a single activity using shared resolution logic."""
        # Use shared parameter resolution
        activity_name, resolved_params = resolve_activity_params(
            stmt=stmt,
            active_vars=active_vars,
            metadata=ctx.metadata,
            workflow_definition_id=ctx.workflow_definition_id,
            workflow_instance_id=ctx.workflow_instance_id,
        )

        activity_path = f"{path}.activity[{activity_name}]"
        self._log(f"[{activity_path}] Executing with params: {list(resolved_params.keys())}")

        # Get activity function
        activity_fn = self.activities.get(activity_name)
        if not activity_fn:
            available = list(self.activities.keys())[:10]
            raise ValueError(
                f"Activity '{activity_name}' not found in registry. "
                f"Available: {available}{'...' if len(self.activities) > 10 else ''}\n"
                f"Hint: Provide the activity via mock_activities or activity_registry parameter."
            )

        # Record benchmark start
        start_time = datetime.now()
        benchmark = ActivityBenchmark(
            name=activity_name,
            path=activity_path,
            start_time=start_time,
            end_time=start_time,
            duration_ms=0,
            status="pending",
            params=resolved_params,
        )

        try:
            # Call activity with dict params (activities expect **kwargs)
            if asyncio.iscoroutinefunction(activity_fn):
                result = await activity_fn(**resolved_params)
            else:
                # Handle sync activities
                result = activity_fn(**resolved_params)

            # Record success
            end_time = datetime.now()
            benchmark.end_time = end_time
            benchmark.duration_ms = (end_time - start_time).total_seconds() * 1000
            benchmark.status = "success"
            benchmark.result = result if isinstance(result, dict) else {"value": result}

            self._log(
                f"[{activity_path}] Completed in {benchmark.duration_ms:.1f}ms"
            )

            # Store result if requested
            if stmt.activity.result:
                active_vars[stmt.activity.result] = result
                self._log(f"[{activity_path}] Stored result in: {stmt.activity.result}")

        except Exception as e:
            # Record error
            end_time = datetime.now()
            benchmark.end_time = end_time
            benchmark.duration_ms = (end_time - start_time).total_seconds() * 1000
            benchmark.status = "error"
            benchmark.error = str(e)

            self._log(f"[{activity_path}] Failed: {e}", level="ERROR")
            raise

        finally:
            ctx.benchmarks.append(benchmark)

    async def _execute_foreach(
        self,
        stmt: ForEachStatement,
        ctx: ExecutionContext,
        path: str,
        active_vars: Dict[str, Any],
    ) -> None:
        """Execute a forEach statement with concurrency control."""
        # Use shared forEach resolution
        items_var, items, item_variable, max_concurrent_config = resolve_foreach_items(
            stmt=stmt,
            active_vars=active_vars,
        )

        foreach_path = f"{path}.foreach[{items_var}]"

        if not items:
            self._log(f"[{foreach_path}] Empty items list, skipping")
            return

        max_concurrent = max_concurrent_config or len(items)
        self._log(
            f"[{foreach_path}] Processing {len(items)} items "
            f"(max_concurrent: {max_concurrent})"
        )

        # Use semaphore for concurrency control
        semaphore = asyncio.Semaphore(max_concurrent)

        async def process_item(index: int, item: Any):
            async with semaphore:
                # Create isolated variable scope
                iteration_vars = create_iteration_vars(active_vars, item_variable, item)

                item_path = f"{foreach_path}.item[{index}]"
                self._log(f"[{item_path}] Starting")

                await self._execute_statement(
                    stmt.foreach.statement,
                    ctx,
                    item_path,
                    iteration_vars
                )

                self._log(f"[{item_path}] Completed")

        # Run all iterations with concurrency limit
        await asyncio.gather(*[
            process_item(i, item) for i, item in enumerate(items)
        ])

        self._log(f"[{foreach_path}] All {len(items)} items completed")

    def get_benchmarks(self, ctx: ExecutionContext) -> List[ActivityBenchmark]:
        """Get all activity benchmarks from an execution context."""
        return ctx.benchmarks

    def print_benchmark_report(self, benchmarks: List[ActivityBenchmark]) -> None:
        """Print a formatted benchmark report."""
        if not benchmarks:
            print("No benchmarks recorded")
            return

        # Group by activity name
        by_name: Dict[str, List[ActivityBenchmark]] = {}
        for b in benchmarks:
            by_name.setdefault(b.name, []).append(b)

        print("=" * 80)
        print("BENCHMARK REPORT")
        print("=" * 80)
        print()
        print(f"{'Activity':<40} {'Count':>6} {'Total(ms)':>12} {'Avg(ms)':>10} {'Max(ms)':>10}")
        print("-" * 80)

        total_duration = 0
        total_count = 0

        for name, items in sorted(by_name.items()):
            count = len(items)
            total_ms = sum(b.duration_ms for b in items)
            avg_ms = total_ms / count if count > 0 else 0
            max_ms = max(b.duration_ms for b in items)

            print(f"{name:<40} {count:>6} {total_ms:>12,.0f} {avg_ms:>10,.0f} {max_ms:>10,.0f}")

            total_duration += total_ms
            total_count += count

        print("-" * 80)
        print(f"Total activities: {total_count}")
        print(f"Total duration: {total_duration:,.0f}ms ({total_duration/1000:.1f}s)")
        print("=" * 80)
