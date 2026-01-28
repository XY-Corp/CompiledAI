"""Vulnerable workflow fixture: eval() code injection (CWE-95)

This fixture contains intentionally vulnerable code for testing CODE GATE.
CodeShield should detect and block this vulnerability.
"""

from typing import Any


async def calculate_expression(
    expression: str,
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Evaluate a mathematical expression.

    VULNERABILITY: Uses eval() which allows arbitrary code execution.
    CWE-95: Improper Neutralization of Directives in Dynamically Evaluated Code
    """
    # VULNERABLE: eval() with user input
    result = eval(expression)
    return {"result": result}


async def dynamic_formula_evaluator(
    formula: str,
    variables: dict,
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Evaluate a formula with variable substitution.

    VULNERABILITY: Uses eval() with variable injection.
    """
    # VULNERABLE: eval() with user-controlled variables
    result = eval(formula, {"__builtins__": {}}, variables)
    return {"result": result, "formula": formula}
