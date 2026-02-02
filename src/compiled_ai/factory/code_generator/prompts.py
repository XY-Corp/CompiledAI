"""Prompt templates for code generation.

This module contains all prompt templates used by the CodeGenerator.
Prompts are designed for precise, per-activity code generation.
"""

# Phase 1: YAML Planning Prompt
YAML_PLANNING_PROMPT = """Generate a workflow YAML specification for the following task.

## Task Description
{task_description}

## Required YAML Structure
Create a file named `workflow.yaml` with the following structure:

```yaml
workflow_id: <unique_snake_case_identifier>
name: <Human Readable Workflow Name>
description: |
  <Multi-line description of what this workflow accomplishes
   and any important details about its behavior.>

# Input variables for the workflow
variables:
  - name: <input_var_name>
    type: <python_type>  # str, int, float, bool, list, dict, or specific like list[str]
    description: <What this variable represents>
    default_value: null  # or a sensible default
    required: true  # or false

# Activities that make up the workflow - EACH MUST HAVE PRECISE SPEC
activities:
  - name: <activity_function_name>  # snake_case, will be the Python function name
    goal: <Clear single-sentence purpose - what this activity accomplishes>
    inputs:
      - name: <param_name>
        type: <python_type>  # Exact Python type annotation
        description: <Detailed description of this parameter>
    output:
      type: <return_type>  # Exact Python type annotation
      description: <What the return value represents and its structure>
    result_variable: <variable_name_to_store_result>  # For downstream activities

# How activities are executed
execution_pattern: sequence  # or: parallel, foreach
# For foreach: add 'foreach_variable: list_var_name'
```

## Guidelines for Activity Specs
- **name**: Use snake_case, will be the exact Python function name
- **goal**: Single sentence describing the activity's purpose (not implementation)
- **inputs**: Each input must have exact Python type annotation
- **output**: Must have exact Python return type annotation
- **result_variable**: Used to pass data to downstream activities

## Example Activity Spec
```yaml
- name: validate_email_format
  goal: Check if email string matches standard email format
  inputs:
    - name: email
      type: str
      description: The email address string to validate
  output:
    type: bool
    description: True if email matches valid format, False otherwise
  result_variable: is_valid_email
```

Save ONLY the YAML content to: workflow.yaml
"""

# Phase 2: Per-Activity Code Generation Prompt
ACTIVITY_GENERATION_PROMPT = """Generate a Python function for this specific activity.

## Activity Specification
Name: {name}
Goal: {goal}

## Input Parameters
{inputs}

## Output
Type: {output_type}
Description: {output_description}

## Requirements
1. **Exact Signature**: Function must be named `{name}` with parameters matching the inputs exactly
2. **Type Hints**: Full type annotations for all parameters and return value
3. **Docstring**: Google-style docstring with Args, Returns, and Raises sections
4. **Input Validation**: Validate inputs and raise appropriate exceptions for invalid data
5. **Return Type**: Return value must match the specified output type exactly
6. **Pure Function**: No side effects, no file I/O, no network calls unless explicitly required

## Output Format
Generate ONLY the Python function, no imports, no test code. Example:

```python
def {name}({signature}) -> {output_type}:
    \"\"\"<One-line description matching the goal>.

    <Extended description if needed>

    Args:
        param1: <Description of param1>
        param2: <Description of param2>

    Returns:
        <Description of return value>

    Raises:
        ValueError: <When raised>
        TypeError: <When raised>
    \"\"\"
    # Input validation
    ...

    # Implementation
    ...

    return result
```

Generate the function now:
"""

# Phase 3: Fix/Retry Prompt
ACTIVITY_FIX_PROMPT = """Fix the validation errors in this activity function.

## Activity Specification
Name: {name}
Goal: {goal}
Expected Input Types: {input_types}
Expected Output Type: {output_type}

## Current Code
```python
{current_code}
```

## Validation Errors
{validation_errors}

## Requirements
1. Fix ALL validation errors
2. Keep the function name and signature exactly as specified
3. Ensure return type matches `{output_type}`
4. Add any missing input validation
5. Keep the fix minimal - don't over-engineer

Generate ONLY the fixed function code:
"""

# Assembly Prompt - for combining activities
ASSEMBLY_PROMPT = """Combine these activity functions into a single activities.py file.

## Workflow: {workflow_name}
{workflow_description}

## Activity Functions
{activity_code}

## Required Imports
Based on the activity implementations, determine the necessary imports.

## Output Format
Create a complete `activities.py` file with:
1. Module docstring describing the workflow
2. All necessary imports at the top (typing, re, json, etc. as needed)
3. All activity functions in order
4. A test block at the bottom

```python
\"\"\"Activity implementations for {workflow_name}.

{workflow_description}

Generated by CompiledAI Code Generator.
\"\"\"

from typing import Any, Optional, ...
import ...

# Activity functions here...

if __name__ == "__main__":
    import sys

    print("Testing activities...")
    try:
        # Test each activity with sample data
        # ...
        print("All tests passed!")
    except Exception as e:
        print(f"Test failed: {{e}}")
        sys.exit(1)
```

Save to: activities.py
"""

# Validation context for fix prompts
VALIDATION_CONTEXT_TEMPLATE = """
## Additional Context
{context}
"""


def format_activity_prompt(
    name: str,
    goal: str,
    inputs: str,
    output_type: str,
    output_description: str,
) -> str:
    """Format the activity generation prompt.

    Args:
        name: Function name
        goal: Activity goal
        inputs: Formatted input list
        output_type: Return type
        output_description: Description of return value

    Returns:
        Formatted prompt string
    """
    # Build signature from inputs
    input_lines = inputs.strip().split("\n")
    signature_parts = []
    for line in input_lines:
        # Parse "- `name`: type (required)" format
        if line.startswith("- `"):
            # Extract name and type
            parts = line.split("`")
            if len(parts) >= 3:
                param_name = parts[1]
                type_part = parts[2].strip(": ").split()[0] if len(parts[2]) > 2 else "Any"
                signature_parts.append(f"{param_name}: {type_part}")

    signature = ", ".join(signature_parts) if signature_parts else ""

    return ACTIVITY_GENERATION_PROMPT.format(
        name=name,
        goal=goal,
        inputs=inputs,
        output_type=output_type,
        output_description=output_description,
        signature=signature,
    )


def format_fix_prompt(
    name: str,
    goal: str,
    input_types: str,
    output_type: str,
    current_code: str,
    validation_errors: str,
) -> str:
    """Format the activity fix prompt.

    Args:
        name: Function name
        goal: Activity goal
        input_types: Formatted input types
        output_type: Expected return type
        current_code: Current function code
        validation_errors: List of validation errors

    Returns:
        Formatted prompt string
    """
    return ACTIVITY_FIX_PROMPT.format(
        name=name,
        goal=goal,
        input_types=input_types,
        output_type=output_type,
        current_code=current_code,
        validation_errors=validation_errors,
    )
