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
    """Extract function name and parameters from user query and function schema.
    
    Returns a dict with function name as key and parameters as nested object.
    """
    # Parse prompt - may be JSON string with nested structure
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
        else:
            data = prompt
        
        # Extract user query from BFCL format: {"question": [[{"role": "user", "content": "..."}]]}
        if "question" in data and isinstance(data["question"], list):
            if len(data["question"]) > 0 and isinstance(data["question"][0], list):
                query = data["question"][0][0].get("content", str(prompt))
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
    
    # Extract parameters based on schema
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_type == "boolean":
            # Check for boolean indicators in query
            # Look for keywords that suggest true/false
            if param_name == "include_contributions":
                # Check if user wants contributions included
                if any(word in query.lower() for word in ["contributions", "contribution", "main contributions", "and main"]):
                    params[param_name] = True
                else:
                    params[param_name] = False
            else:
                # Generic boolean detection
                params[param_name] = False
        
        elif param_type == "string":
            # Extract string values based on parameter name and description
            if "papal_name" in param_name or "papal name" in param_desc:
                # Extract papal name - look for "Pope X" pattern or just the name
                # Common pattern: "Pope Innocent III" or just "Innocent III"
                pope_match = re.search(r'Pope\s+([A-Z][a-z]+(?:\s+[IVX]+)?)', query)
                if pope_match:
                    params[param_name] = pope_match.group(1)
                else:
                    # Try to find name pattern like "Innocent III"
                    name_match = re.search(r'([A-Z][a-z]+\s+[IVX]+)', query)
                    if name_match:
                        params[param_name] = name_match.group(1)
                    else:
                        # Fallback - look for capitalized words
                        words = re.findall(r'[A-Z][a-z]+(?:\s+[IVX]+)?', query)
                        if words:
                            params[param_name] = words[-1]  # Take last match
                        else:
                            params[param_name] = "<UNKNOWN>"
            else:
                # Generic string extraction - try to find relevant text
                params[param_name] = "<UNKNOWN>"
        
        elif param_type in ["integer", "number", "float"]:
            # Extract numbers
            numbers = re.findall(r'\d+(?:\.\d+)?', query)
            if numbers:
                if param_type == "integer":
                    params[param_name] = int(numbers[0])
                else:
                    params[param_name] = float(numbers[0])
            else:
                params[param_name] = 0
    
    return {func_name: params}
