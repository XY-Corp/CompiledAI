"""DSL model definitions for workflow execution.

These Pydantic models define the structure of DSL workflows that can be
executed by the LocalWorkflowExecutor.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field


class ActivityInvocation(BaseModel):
    """Activity invocation details."""
    name: str  # Activity name (e.g., "extract_pdf_activity")
    params: Dict[str, Any] = Field(default_factory=dict)  # Named parameters (supports ${{ var }})
    result: Optional[str] = None  # Variable name to store result
    timeout_minutes: int = 10  # Activity timeout in minutes (default: 10)


class ActivityStatement(BaseModel):
    """Execute a single activity."""
    activity: ActivityInvocation


class Sequence(BaseModel):
    """Sequence of statements."""
    elements: List[Statement]


class SequenceStatement(BaseModel):
    """Execute statements in sequence."""
    sequence: Sequence


class Parallel(BaseModel):
    """Parallel branches."""
    branches: List[Statement]


class ParallelStatement(BaseModel):
    """Execute statements in parallel."""
    parallel: Parallel


class ForEach(BaseModel):
    """ForEach loop configuration."""
    items: str  # Variable name containing list of items
    statement: Statement  # Statement to execute for each item
    item_variable: str = Field(default="item")  # Variable name for current item
    max_concurrent: Optional[int] = None  # Max concurrent executions (None = unlimited)


class ForEachStatement(BaseModel):
    """Execute statement for each item in a list (dynamic parallel execution)."""
    foreach: ForEach


class ChildWorkflow(BaseModel):
    """Child workflow configuration."""
    statement: Statement  # Statement to execute in child workflow
    workflow_id_prefix: Optional[str] = None  # Optional prefix for child workflow IDs


class ChildWorkflowStatement(BaseModel):
    """Execute statement in a child workflow."""
    child_workflow: ChildWorkflow


# Statement union type
Statement = Union[ActivityStatement, SequenceStatement, ParallelStatement, ForEachStatement, ChildWorkflowStatement]


class ForeachState(BaseModel):
    """
    State for resuming a forEach after continue-as-new.

    Each forEach tracks its own progress independently, allowing multiple
    forEach blocks to auto-continue-as-new without interfering with each other.
    """
    next_idx: int  # Next item index to process
    completed_count: int  # Total items completed (across all CAN executions)
    items_var: str  # Variable name (for validation/debugging)


class DSLInput(BaseModel):
    """
    Input for DSL workflow execution.

    Supports both old-style (config_flow_id) and new-style
    (workflow_definition_id/workflow_instance_id) field names for compatibility.
    """
    # Support both old and new field names
    config_flow_id: Optional[str] = None  # Legacy: workflow ID
    root_config_flow_id: Optional[str] = None  # Legacy: root workflow ID for DB
    workflow_definition_id: Optional[str] = None  # New: definition template ID
    workflow_instance_id: Optional[str] = None  # New: execution instance ID

    root: Statement  # Root DSL statement to execute
    variables: Dict[str, Any] = Field(default_factory=dict)  # Input variables
    metadata: Dict[str, Any] = Field(default_factory=dict)  # user_id, org_id, etc.
    is_child_workflow: bool = False  # Skip status updates for child workflows
    parent_workflow_id: Optional[str] = None  # Parent workflow ID for signaling completion
    foreach_states: Dict[str, ForeachState] = Field(default_factory=dict)  # Per-forEach CAN bookmarks
    from_foreach: bool = False  # Indicates child spawned by forEach (for signal routing)
    foreach_can_page_size: int = 1000  # High value to disable CAN


# Update forward references for recursive types
DSLInput.model_rebuild()
Sequence.model_rebuild()
Parallel.model_rebuild()
ForEach.model_rebuild()
ChildWorkflow.model_rebuild()
