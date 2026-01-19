"""YAML to DSL Pydantic model parser."""
import yaml
from typing import Dict, Any, List, Tuple
from xy_local_executor.dsl.models import (
    DSLInput,
    Statement,
    ActivityStatement,
    SequenceStatement,
    ParallelStatement,
    ForEachStatement,
    ChildWorkflowStatement,
)
from xy_local_executor.dsl.template import validate_name_field


class VariableOverwriteError(ValueError):
    """Raised when a result variable would overwrite an existing variable."""
    pass


# Reserved names that are injected by dsl_workflow.py from trusted metadata
# These cannot be used as result variable names or forEach item_variable names
RESERVED_PARAM_NAMES = frozenset({"org_id", "user_id", "config_flow_id", "workflow_definition_id", "workflow_instance_id"})


def _collect_result_names(statement: Statement, path: str = "root") -> List[Tuple[str, str]]:
    """
    Recursively collect all result variable names from a DSL statement tree.

    Returns list of (result_name, location_path) tuples for error reporting.
    """
    results = []

    if isinstance(statement, ActivityStatement):
        if statement.activity.result:
            results.append((statement.activity.result, f"{path}.activity[{statement.activity.name}]"))

    elif isinstance(statement, SequenceStatement):
        for i, element in enumerate(statement.sequence.elements):
            results.extend(_collect_result_names(element, f"{path}.sequence[{i}]"))

    elif isinstance(statement, ParallelStatement):
        for i, branch in enumerate(statement.parallel.branches):
            results.extend(_collect_result_names(branch, f"{path}.parallel[{i}]"))

    elif isinstance(statement, ForEachStatement):
        # ForEach item_variable is a loop-scoped variable, collect it too
        item_var = statement.foreach.item_variable
        results.append((item_var, f"{path}.foreach.item_variable"))
        # Recurse into the foreach body
        results.extend(_collect_result_names(statement.foreach.statement, f"{path}.foreach.body"))

    elif isinstance(statement, ChildWorkflowStatement):
        results.extend(_collect_result_names(statement.child_workflow.statement, f"{path}.child_workflow"))

    return results


def _validate_name_fields(statement: Statement, path: str = "root") -> None:
    """
    Recursively validate that name fields do not use template syntax.

    Name fields expect raw variable names or literal strings, not ${{ }} template syntax.
    This is a parse-time check to catch YAML authoring errors.

    **Name fields validated:**
    - `result` (ActivityStatement) - Variable name to store activity result
    - `items` (ForEachStatement) - Variable name containing list to iterate
    - `item_variable` (ForEachStatement) - Variable name for current iteration item
    - `workflow_id_prefix` (ChildWorkflowStatement) - Literal string prefix for workflow IDs

    **IMPORTANT:** When adding new DSL statement types or fields that represent
    variable names or literal identifiers (not data values), add validation here.
    Only `params` values should use ${{ }} syntax.

    Args:
        statement: DSL statement to validate
        path: Current path in DSL tree (for error messages)

    Raises:
        ValueError: If template syntax is used in a name field
    """
    if isinstance(statement, ActivityStatement):
        # Validate 'result' field if present
        if statement.activity.result:
            validate_name_field(
                statement.activity.result,
                "result",
                f"{path}.activity[{statement.activity.name}]"
            )

    elif isinstance(statement, SequenceStatement):
        for i, element in enumerate(statement.sequence.elements):
            _validate_name_fields(element, f"{path}.sequence[{i}]")

    elif isinstance(statement, ParallelStatement):
        for i, branch in enumerate(statement.parallel.branches):
            _validate_name_fields(branch, f"{path}.parallel[{i}]")

    elif isinstance(statement, ForEachStatement):
        # Validate 'items' field
        validate_name_field(
            statement.foreach.items,
            "items",
            f"{path}.foreach"
        )
        # Validate 'item_variable' field
        validate_name_field(
            statement.foreach.item_variable,
            "item_variable",
            f"{path}.foreach"
        )
        # Recurse into the foreach body
        _validate_name_fields(statement.foreach.statement, f"{path}.foreach.body")

    elif isinstance(statement, ChildWorkflowStatement):
        # Validate 'workflow_id_prefix' field if present
        if statement.child_workflow.workflow_id_prefix:
            validate_name_field(
                statement.child_workflow.workflow_id_prefix,
                "workflow_id_prefix",
                f"{path}.child_workflow"
            )
        # Recurse into the child workflow body
        _validate_name_fields(statement.child_workflow.statement, f"{path}.child_workflow")


def validate_no_variable_overwrites(dsl_input: DSLInput) -> None:
    """
    Validate that no result variables overwrite initial variables or each other.

    This is a parse-time check to catch YAML authoring errors before runtime.

    Raises:
        VariableOverwriteError: If any result variable would overwrite another
    """
    # Collect initial variable names
    initial_vars = set(dsl_input.variables.keys())

    # Collect all result names from the DSL tree
    result_entries = _collect_result_names(dsl_input.root)

    # Check for collisions with reserved injected params (org_id, user_id, etc.)
    for result_name, location in result_entries:
        if result_name in RESERVED_PARAM_NAMES:
            raise VariableOverwriteError(
                f"Reserved name '{result_name}' at {location} cannot be used as a result variable. "
                f"These names are injected by the workflow from trusted metadata: {sorted(RESERVED_PARAM_NAMES)}"
            )

    # Check for collisions with initial variables
    for result_name, location in result_entries:
        if result_name in initial_vars:
            raise VariableOverwriteError(
                f"Variable overwrite detected: result '{result_name}' at {location} "
                f"would overwrite initial variable '{result_name}'. "
                f"Use a unique name for the result."
            )

    # Check for duplicate result names (same name defined multiple times)
    seen_results: Dict[str, str] = {}  # name -> first location
    for result_name, location in result_entries:
        if result_name in seen_results:
            raise VariableOverwriteError(
                f"Duplicate result variable: '{result_name}' is defined at both "
                f"{seen_results[result_name]} and {location}. "
                f"Each result must have a unique name."
            )
        seen_results[result_name] = location


def build_dsl_input(
    config_flow_id: str,
    execution_yaml: str,
    input_data: Dict[str, Any],
    metadata: Dict[str, Any]
) -> DSLInput:
    """
    Build DSLInput from YAML and input data.

    Args:
        config_flow_id: Workflow ID (used for logging/tracking)
        execution_yaml: YAML workflow definition
        input_data: Runtime input variables
        metadata: Context metadata (user_id, org_id, etc.)

    Returns:
        DSLInput ready for execution

    Raises:
        ValueError: If execution YAML is missing required fields or has invalid structure
        yaml.YAMLError: If YAML is malformed
        pydantic.ValidationError: If structure doesn't match DSLInput schema
        VariableOverwriteError: If result variables would overwrite existing variables
        ValueError: If template syntax is used in name fields (items, result, item_variable)

    Example:
        ```python
        dsl_input = build_dsl_input(
            config_flow_id="workflow_123",
            execution_yaml=yaml_content,
            input_data={"file_path": "/path/to/file.pdf"},
            metadata={"user_id": "user_123", "org_id": "org_456"}
        )
        ```
    """
    # Parse the execution YAML to get the root statement structure
    parsed = yaml.safe_load(execution_yaml)

    # Extract root statement (required)
    if "root" not in parsed:
        raise ValueError("Execution YAML must contain 'root' statement")

    # Build DSLInput by combining parsed YAML with runtime data
    dsl_input_dict = {
        "config_flow_id": config_flow_id,
        "root": parsed["root"],
        "variables": {
            # Start with variables from YAML (defaults)
            **parsed.get("variables", {}),
            # Override with runtime input data
            **input_data,
        },
        "metadata": metadata,
    }

    # Convert to Pydantic model with validation
    dsl_input = DSLInput.model_validate(dsl_input_dict)

    # Validate no variable overwrites
    validate_no_variable_overwrites(dsl_input)

    # Validate name fields don't use template syntax
    _validate_name_fields(dsl_input.root)

    return dsl_input
