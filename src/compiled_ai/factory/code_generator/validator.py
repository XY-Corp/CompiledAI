"""Code validation for generated activities.

This module validates that generated code matches the activity specifications.
It uses AST parsing to verify function signatures, types, and structure.
"""

import ast
import logging
from dataclasses import dataclass, field
from typing import Optional

from .models import ActivitySpec

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of validating generated code against a spec."""

    valid: bool
    """Whether the code passes all validation checks."""

    errors: list[str] = field(default_factory=list)
    """List of validation error messages."""

    warnings: list[str] = field(default_factory=list)
    """List of non-fatal validation warnings."""

    def __bool__(self) -> bool:
        """Allow using result in boolean context."""
        return self.valid


def find_function(tree: ast.Module, name: str) -> Optional[ast.FunctionDef]:
    """Find a function definition by name in an AST.

    Args:
        tree: Parsed AST module
        name: Function name to find

    Returns:
        FunctionDef node if found, None otherwise
    """
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


def get_type_annotation_str(annotation: ast.expr | None) -> str:
    """Convert an AST annotation node to a string representation.

    Args:
        annotation: AST annotation node

    Returns:
        String representation of the type annotation
    """
    if annotation is None:
        return "Any"

    # Handle simple names like str, int, bool
    if isinstance(annotation, ast.Name):
        return annotation.id

    # Handle subscript types like list[str], dict[str, int]
    if isinstance(annotation, ast.Subscript):
        base = get_type_annotation_str(annotation.value)
        # Handle the slice
        if isinstance(annotation.slice, ast.Tuple):
            # Multiple type params like dict[str, int]
            params = ", ".join(
                get_type_annotation_str(elt) for elt in annotation.slice.elts
            )
            return f"{base}[{params}]"
        else:
            # Single type param like list[str]
            param = get_type_annotation_str(annotation.slice)
            return f"{base}[{param}]"

    # Handle Constant for string annotations
    if isinstance(annotation, ast.Constant) and isinstance(annotation.value, str):
        return annotation.value

    # Handle BinOp for Union types (X | Y)
    if isinstance(annotation, ast.BinOp) and isinstance(annotation.op, ast.BitOr):
        left = get_type_annotation_str(annotation.left)
        right = get_type_annotation_str(annotation.right)
        return f"{left} | {right}"

    # Handle Attribute for qualified names like typing.Optional
    if isinstance(annotation, ast.Attribute):
        value = get_type_annotation_str(annotation.value)
        return f"{value}.{annotation.attr}"

    return "Any"


def normalize_type(type_str: str) -> str:
    """Normalize a type string for comparison.

    Handles common variations like:
    - Optional[X] vs X | None
    - List vs list
    - Dict vs dict

    Args:
        type_str: Type annotation string

    Returns:
        Normalized type string for comparison
    """
    # Remove whitespace
    type_str = type_str.replace(" ", "")

    # Lowercase common types
    type_str = type_str.replace("List", "list")
    type_str = type_str.replace("Dict", "dict")
    type_str = type_str.replace("Tuple", "tuple")
    type_str = type_str.replace("Set", "set")

    # Normalize Optional[X] to X|None
    if type_str.startswith("Optional[") and type_str.endswith("]"):
        inner = type_str[9:-1]
        type_str = f"{inner}|None"

    # Sort union types for consistent comparison
    if "|" in type_str:
        parts = sorted(type_str.split("|"))
        type_str = "|".join(parts)

    return type_str


def types_match(expected: str, actual: str) -> bool:
    """Check if two type annotations are equivalent.

    Args:
        expected: Expected type annotation
        actual: Actual type annotation from code

    Returns:
        True if types are equivalent
    """
    return normalize_type(expected) == normalize_type(actual)


def validate_activity(code: str, spec: ActivitySpec) -> ValidationResult:
    """Validate that generated code matches the activity specification.

    Checks:
    - Function exists with correct name
    - Parameters match spec inputs (names and types)
    - Return type matches spec output
    - Docstring is present

    Args:
        code: Generated Python code
        spec: Activity specification to validate against

    Returns:
        ValidationResult with any errors found
    """
    errors: list[str] = []
    warnings: list[str] = []

    # Parse the code
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return ValidationResult(
            valid=False,
            errors=[f"Syntax error: {e}"],
        )

    # Find the function
    func = find_function(tree, spec.name)
    if func is None:
        return ValidationResult(
            valid=False,
            errors=[f"Function '{spec.name}' not found in generated code"],
        )

    # Check parameters
    func_args = func.args
    spec_inputs = {inp.name: inp for inp in spec.inputs}
    func_params = {}

    # Collect function parameters
    for arg in func_args.args:
        param_name = arg.arg
        param_type = get_type_annotation_str(arg.annotation)
        func_params[param_name] = param_type

    # Check for missing parameters
    for input_name, input_spec in spec_inputs.items():
        if input_name not in func_params:
            errors.append(f"Missing parameter: '{input_name}'")
        else:
            actual_type = func_params[input_name]
            expected_type = input_spec.type
            if not types_match(expected_type, actual_type):
                errors.append(
                    f"Parameter '{input_name}' type mismatch: "
                    f"expected '{expected_type}', got '{actual_type}'"
                )

    # Check for extra parameters (warning, not error)
    for param_name in func_params:
        if param_name not in spec_inputs and param_name != "self":
            warnings.append(f"Extra parameter not in spec: '{param_name}'")

    # Check return type
    return_annotation = get_type_annotation_str(func.returns)
    if not types_match(spec.output.type, return_annotation):
        errors.append(
            f"Return type mismatch: expected '{spec.output.type}', got '{return_annotation}'"
        )

    # Check for docstring
    docstring = ast.get_docstring(func)
    if not docstring:
        warnings.append("Function is missing a docstring")

    return ValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )


def validate_syntax(code: str) -> ValidationResult:
    """Validate that code has valid Python syntax.

    Args:
        code: Python code to validate

    Returns:
        ValidationResult with syntax errors if any
    """
    try:
        ast.parse(code)
        return ValidationResult(valid=True)
    except SyntaxError as e:
        return ValidationResult(
            valid=False,
            errors=[f"Syntax error at line {e.lineno}: {e.msg}"],
        )


def validate_imports(code: str) -> ValidationResult:
    """Validate that all imports are resolvable.

    Args:
        code: Python code to validate

    Returns:
        ValidationResult with import errors if any
    """
    errors: list[str] = []

    try:
        tree = ast.parse(code)
    except SyntaxError:
        return ValidationResult(valid=False, errors=["Cannot parse code"])

    # Check imports
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                try:
                    __import__(alias.name)
                except ImportError:
                    errors.append(f"Cannot import module: '{alias.name}'")

        elif isinstance(node, ast.ImportFrom):
            if node.module:
                try:
                    __import__(node.module)
                except ImportError:
                    errors.append(f"Cannot import from module: '{node.module}'")

    return ValidationResult(valid=len(errors) == 0, errors=errors)


def extract_function_code(code: str, func_name: str) -> Optional[str]:
    """Extract just the code for a specific function.

    Args:
        code: Full Python code
        func_name: Name of function to extract

    Returns:
        Just the function code, or None if not found
    """
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return None

    func = find_function(tree, func_name)
    if func is None:
        return None

    # Get the source lines
    lines = code.split("\n")
    start_line = func.lineno - 1  # AST uses 1-indexed lines
    end_line = func.end_lineno if func.end_lineno else len(lines)

    return "\n".join(lines[start_line:end_line])
