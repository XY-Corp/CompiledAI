"""Shared DSL execution utilities.

This module contains logic for DSL workflow execution including:
- Parameter resolution and injection
- Statement validation
- Variable scoping rules
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from xy_local_executor.dsl.models import (
    Statement,
    ActivityStatement,
    SequenceStatement,
    ParallelStatement,
    ForEachStatement,
    ChildWorkflowStatement,
)
from xy_local_executor.dsl.template import resolve_templates, _resolve_path


class DSLExecutionError(Exception):
    """Base exception for DSL execution errors."""
    def __init__(self, message: str, error_type: str = "DSLError"):
        super().__init__(message)
        self.error_type = error_type


class TemplateResolutionError(DSLExecutionError):
    """Error resolving ${{ }} templates."""
    def __init__(self, message: str):
        super().__init__(message, "TemplateResolutionError")


class DSLStructureError(DSLExecutionError):
    """Error in DSL structure."""
    def __init__(self, message: str):
        super().__init__(message, "DSLStructureError")


def resolve_activity_params(
    stmt: ActivityStatement,
    active_vars: Dict[str, Any],
    metadata: Dict[str, Any],
    workflow_definition_id: str,
    workflow_instance_id: str,
) -> Tuple[str, Dict[str, Any]]:
    """
    Resolve activity parameters from a statement.

    Args:
        stmt: The ActivityStatement to resolve
        active_vars: Current variable context
        metadata: Workflow metadata (user_id, organization_id)
        workflow_definition_id: The workflow definition ID (the template)
        workflow_instance_id: The workflow instance ID (the execution)

    Returns:
        Tuple of (activity_name, resolved_params)

    Raises:
        DSLStructureError: If activity name is missing or params is not a dict
        TemplateResolutionError: If template resolution fails
    """
    activity_name = stmt.activity.name

    if not activity_name:
        raise DSLStructureError("Activity 'name' is required in DSL statement")

    raw_params = stmt.activity.params or {}
    if not isinstance(raw_params, dict):
        raise DSLStructureError(
            f"'params' for activity '{activity_name}' must be a mapping, "
            f"got {type(raw_params).__name__}"
        )

    # 1) Resolve ${{ var }} templates against the active variable context
    try:
        resolved_params = resolve_templates(raw_params, active_vars)
    except (KeyError, ValueError) as e:
        raise TemplateResolutionError(
            f"Template resolution failed for activity '{activity_name}': {str(e)}"
        ) from e

    # 2) Inject trusted context (security: always use trusted source, not YAML)
    if metadata.get("organization_id"):
        resolved_params["org_id"] = metadata["organization_id"]
    if metadata.get("user_id"):
        resolved_params["user_id"] = metadata["user_id"]
    resolved_params["workflow_definition_id"] = workflow_definition_id
    resolved_params["workflow_instance_id"] = workflow_instance_id

    return activity_name, resolved_params


def resolve_foreach_items(
    stmt: ForEachStatement,
    active_vars: Dict[str, Any],
) -> Tuple[str, list, str, Optional[int]]:
    """
    Resolve forEach items and configuration.

    Args:
        stmt: The ForEachStatement to resolve
        active_vars: Current variable context

    Returns:
        Tuple of (items_var, items_list, item_variable_name, max_concurrent)

    Raises:
        TemplateResolutionError: If items variable cannot be resolved
        DSLStructureError: If items is not a list
    """
    items_var = stmt.foreach.items

    # Support dotted paths like "outer_item.sub_items"
    try:
        items = _resolve_path(items_var, active_vars)
    except (KeyError, ValueError) as e:
        raise TemplateResolutionError(
            f"ForEach items variable '{items_var}' could not be resolved.\n"
            f"Error: {e}\n\n"
            f"The 'items' field expects a variable name containing a list.\n"
            f"Dot notation is supported for nested access (e.g., order.line_items)."
        ) from e

    if not isinstance(items, list):
        raise DSLStructureError(
            f"ForEach items variable '{items_var}' must be a list, got {type(items)}"
        )

    return (
        items_var,
        items,
        stmt.foreach.item_variable,
        stmt.foreach.max_concurrent,
    )


def create_iteration_vars(
    active_vars: Dict[str, Any],
    item_variable: str,
    item: Any,
) -> Dict[str, Any]:
    """
    Create isolated variable scope for a forEach iteration.

    Args:
        active_vars: Current variable context
        item_variable: Name of the iteration variable
        item: Value for this iteration

    Returns:
        New variable dict with isolated scope
    """
    iteration_vars = dict(active_vars)
    iteration_vars[item_variable] = item
    return iteration_vars


def get_statement_type(stmt: Statement) -> str:
    """
    Get the type name of a DSL statement.

    Args:
        stmt: The statement to check

    Returns:
        Type name string: "activity", "sequence", "parallel", "foreach", "child_workflow"
    """
    if isinstance(stmt, ActivityStatement):
        return "activity"
    elif isinstance(stmt, SequenceStatement):
        return "sequence"
    elif isinstance(stmt, ParallelStatement):
        return "parallel"
    elif isinstance(stmt, ForEachStatement):
        return "foreach"
    elif isinstance(stmt, ChildWorkflowStatement):
        return "child_workflow"
    else:
        return "unknown"


def get_statement_info(stmt: Statement) -> Dict[str, Any]:
    """
    Get descriptive info about a statement for logging.

    Args:
        stmt: The statement to describe

    Returns:
        Dict with statement metadata
    """
    stmt_type = get_statement_type(stmt)
    info = {"type": stmt_type}

    if isinstance(stmt, ActivityStatement):
        info["name"] = stmt.activity.name
        info["has_result"] = bool(stmt.activity.result)
    elif isinstance(stmt, SequenceStatement):
        info["element_count"] = len(stmt.sequence.elements)
    elif isinstance(stmt, ParallelStatement):
        info["branch_count"] = len(stmt.parallel.branches)
    elif isinstance(stmt, ForEachStatement):
        info["items_var"] = stmt.foreach.items
        info["item_variable"] = stmt.foreach.item_variable
        info["max_concurrent"] = stmt.foreach.max_concurrent
    elif isinstance(stmt, ChildWorkflowStatement):
        info["prefix"] = stmt.child_workflow.workflow_id_prefix

    return info
