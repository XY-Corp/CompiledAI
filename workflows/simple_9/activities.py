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
    """Extract function call parameters from natural language prompt.
    
    Parses the prompt to extract the user query, identifies the target function,
    and extracts parameter values using regex patterns.
    
    Args:
        prompt: The input prompt containing the user query (may be JSON string)
        functions: List of available function definitions with parameter schemas
        
    Returns:
        Dict with function name as key and extracted parameters as nested dict
    """
    # Parse prompt - may be JSON string with nested structure
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
            # Handle BFCL format: {"question": [[{"role": "user", "content": "..."}]], ...}
            if "question" in data and isinstance(data["question"], list):
                if len(data["question"]) > 0 and isinstance(data["question"][0], list):
                    if len(data["question"][0]) > 0:
                        query = data["question"][0][0].get("content", str(prompt))
                    else:
                        query = str(prompt)
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
    
    # Get target function details
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    required_params = func.get("parameters", {}).get("required", [])
    
    # Extract parameters based on schema
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_type == "integer" or param_type == "number":
            # Extract numbers from query using regex
            # Look for patterns like "radius of 5" or "with a radius of 5"
            # Try specific patterns first
            patterns = [
                rf'{param_name}\s+(?:of\s+)?(\d+(?:\.\d+)?)',  # "radius of 5" or "radius 5"
                rf'(?:a|the)\s+{param_name}\s+(?:of\s+)?(\d+(?:\.\d+)?)',  # "a radius of 5"
                rf'(\d+(?:\.\d+)?)\s+(?:unit|units)?\s*{param_name}',  # "5 unit radius"
                rf'with\s+(?:a\s+)?{param_name}\s+(?:of\s+)?(\d+(?:\.\d+)?)',  # "with a radius of 5"
            ]
            
            value = None
            for pattern in patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    value = match.group(1)
                    break
            
            # Fallback: extract any number if this is a required param
            if value is None and param_name in required_params:
                numbers = re.findall(r'\d+(?:\.\d+)?', query)
                if numbers:
                    value = numbers[0]
            
            if value is not None:
                if param_type == "integer":
                    params[param_name] = int(float(value))
                else:
                    params[param_name] = float(value)
                    
        elif param_type == "string":
            # For optional string params like "unit", check if mentioned
            # Look for unit mentions
            if "unit" in param_name.lower() or "unit" in param_desc:
                unit_patterns = [
                    r'in\s+(\w+)',  # "in meters"
                    r'(\w+)\s+units?',  # "meter units"
                    r'unit[s]?\s+(?:is|are|of)\s+(\w+)',  # "units of meters"
                ]
                for pattern in unit_patterns:
                    match = re.search(pattern, query, re.IGNORECASE)
                    if match:
                        unit_val = match.group(1).lower()
                        # Filter out common non-unit words
                        if unit_val not in ['a', 'the', 'of', 'with', 'and', 'or']:
                            params[param_name] = unit_val
                            break
            else:
                # Generic string extraction - look for quoted strings or after "of"
                quoted = re.search(r'"([^"]+)"', query)
                if quoted:
                    params[param_name] = quoted.group(1)
    
    return {func_name: params}
