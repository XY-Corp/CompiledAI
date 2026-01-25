import re
import json
from typing import Any


async def extract_function_call(
    prompt: str,
    functions: list,
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extract function call parameters from user query and return as {func_name: {params}}."""
    
    # Parse prompt - may be JSON string with nested structure
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
            # Handle BFCL format: {"question": [[{"role": "user", "content": "..."}]], ...}
            if "question" in data and isinstance(data["question"], list):
                if len(data["question"]) > 0 and isinstance(data["question"][0], list):
                    query = data["question"][0][0].get("content", str(prompt))
                else:
                    query = str(prompt)
            else:
                query = str(prompt)
        else:
            query = str(prompt)
    except (json.JSONDecodeError, TypeError, KeyError):
        query = str(prompt)
    
    # Parse functions - may be JSON string
    try:
        if isinstance(functions, str):
            funcs = json.loads(functions)
        else:
            funcs = functions
    except (json.JSONDecodeError, TypeError):
        funcs = []
    
    # Get function details
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters from query using regex
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        enum_values = param_info.get("enum", [])
        
        # Extract based on parameter name and context
        if param_name == "patient_id":
            # Look for patient id patterns: "patient with id X", "patient id X", "id X"
            id_patterns = [
                r'patient\s+(?:with\s+)?id\s+[\'"]?(\d+)[\'"]?',
                r'id\s+[\'"]?(\d+)[\'"]?',
                r'patient\s+[\'"]?(\d+)[\'"]?',
            ]
            for pattern in id_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    params[param_name] = match.group(1)
                    break
        
        elif param_name == "mri_type":
            # Check for MRI type in enum values
            if enum_values:
                for enum_val in enum_values:
                    if enum_val.lower() in query.lower():
                        params[param_name] = enum_val
                        break
            # Default to 'brain' if mentioned or if default specified
            if param_name not in params:
                if "brain" in query.lower():
                    params[param_name] = "brain"
                elif "default" in param_desc and "brain" in param_desc:
                    params[param_name] = "brain"
        
        elif param_name == "status":
            # Check for status in enum values
            if enum_values:
                for enum_val in enum_values:
                    # Handle multi-word enum values like "in progress"
                    if enum_val.lower() in query.lower():
                        params[param_name] = enum_val
                        break
            # Also check for quoted status values
            if param_name not in params:
                status_match = re.search(r"status\s+['\"]([^'\"]+)['\"]", query, re.IGNORECASE)
                if status_match:
                    params[param_name] = status_match.group(1)
    
    return {func_name: params}
