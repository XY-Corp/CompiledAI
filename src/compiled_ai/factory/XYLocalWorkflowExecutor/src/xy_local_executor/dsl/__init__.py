"""DSL module for workflow definition and parsing."""

from xy_local_executor.dsl.models import (
    DSLInput,
    Statement,
    ActivityStatement,
    ActivityInvocation,
    SequenceStatement,
    Sequence,
    ParallelStatement,
    Parallel,
    ForEachStatement,
    ForEach,
    ChildWorkflowStatement,
    ChildWorkflow,
    ForeachState,
)
from xy_local_executor.dsl.parser import build_dsl_input, VariableOverwriteError
from xy_local_executor.dsl.template import resolve_templates, resolve_template_scalar
from xy_local_executor.dsl.execution import (
    resolve_activity_params,
    resolve_foreach_items,
    create_iteration_vars,
    DSLExecutionError,
    TemplateResolutionError,
    DSLStructureError,
)

__all__ = [
    # Models
    "DSLInput",
    "Statement",
    "ActivityStatement",
    "ActivityInvocation",
    "SequenceStatement",
    "Sequence",
    "ParallelStatement",
    "Parallel",
    "ForEachStatement",
    "ForEach",
    "ChildWorkflowStatement",
    "ChildWorkflow",
    "ForeachState",
    # Parser
    "build_dsl_input",
    "VariableOverwriteError",
    # Template
    "resolve_templates",
    "resolve_template_scalar",
    # Execution
    "resolve_activity_params",
    "resolve_foreach_items",
    "create_iteration_vars",
    "DSLExecutionError",
    "TemplateResolutionError",
    "DSLStructureError",
]
