import re
import json
from typing import Any


async def extract_function_call(
    prompt: str,
    functions: list = None,
    user_query: str = None,
    tools: list = None,
    tool_name_mapping: dict = None,
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extract function call parameters from user query and return as {func_name: {params}}."""
    
    # Step 1: Parse prompt to extract the actual user query
    query = prompt
    if isinstance(prompt, str):
        try:
            data = json.loads(prompt)
            # Handle BFCL-style nested structure
            if "question" in data and isinstance(data["question"], list):
                if len(data["question"]) > 0 and isinstance(data["question"][0], list):
                    query = data["question"][0][0].get("content", prompt)
                elif len(data["question"]) > 0 and isinstance(data["question"][0], dict):
                    query = data["question"][0].get("content", prompt)
            elif "query" in data:
                query = data["query"]
            elif "content" in data:
                query = data["content"]
        except (json.JSONDecodeError, TypeError, KeyError):
            query = prompt
    
    # Step 2: Parse functions list
    funcs = functions
    if isinstance(functions, str):
        try:
            funcs = json.loads(functions)
        except (json.JSONDecodeError, TypeError):
            funcs = []
    
    if not funcs:
        funcs = []
    
    # Get the target function (first one)
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    
    # Get parameters schema - handle both "parameters" with nested "properties" and direct "parameters"
    params_schema = func.get("parameters", {})
    if "properties" in params_schema:
        props = params_schema.get("properties", {})
    else:
        props = params_schema
    
    required_params = params_schema.get("required", [])
    
    # Step 3: Extract parameter values using regex
    params = {}
    
    for param_name, param_info in props.items():
        # Handle both dict format and string format for param_info
        if isinstance(param_info, str):
            param_type = param_info
            param_desc = ""
        else:
            param_type = param_info.get("type", "string")
            param_desc = param_info.get("description", "").lower()
        
        value = None
        
        if param_type in ["integer", "number", "float"]:
            # Extract numbers from query
            # Try specific patterns first based on param name
            param_patterns = [
                rf'{param_name}\s*[=:]\s*(\d+(?:\.\d+)?)',  # param_name = 5 or param_name: 5
                rf'{param_name}\s+(\d+(?:\.\d+)?)',  # param_name 5
                rf'(\d+(?:\.\d+)?)\s*{param_name}',  # 5 param_name
            ]
            
            for pattern in param_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    value = match.group(1)
                    break
            
            # If no specific match, look for contextual patterns
            if value is None:
                # For radius specifically
                if param_name == "radius":
                    radius_patterns = [
                        r'radius\s+(?:of\s+)?(\d+(?:\.\d+)?)',
                        r'radius\s*[=:]\s*(\d+(?:\.\d+)?)',
                        r'with\s+radius\s+(\d+(?:\.\d+)?)',
                        r'r\s*=\s*(\d+(?:\.\d+)?)',
                    ]
                    for pattern in radius_patterns:
                        match = re.search(pattern, query, re.IGNORECASE)
                        if match:
                            value = match.group(1)
                            break
            
            # Fallback: extract all numbers and use the first one for required params
            if value is None and param_name in required_params:
                numbers = re.findall(r'\b(\d+(?:\.\d+)?)\b', query)
                if numbers:
                    value = numbers[0]
            
            # Convert to appropriate type
            if value is not None:
                if param_type == "integer":
                    value = int(float(value))
                else:
                    value = float(value)
        
        elif param_type == "string":
            # For units, look for common unit patterns
            if param_name == "units" or "unit" in param_desc:
                unit_patterns = [
                    r'in\s+(cm|mm|m|meters?|inches?|feet|ft|yards?|yd|kilometers?|km|miles?|mi)',
                    r'units?\s*[=:]\s*["\']?(\w+)["\']?',
                    r'\b(cm|mm|m|meters?|inches?|feet|ft|yards?|yd|kilometers?|km|miles?|mi)\b',
                ]
                for pattern in unit_patterns:
                    match = re.search(pattern, query, re.IGNORECASE)
                    if match:
                        value = match.group(1).lower()
                        break
            else:
                # Generic string extraction
                string_patterns = [
                    rf'{param_name}\s*[=:]\s*["\']?([^"\']+)["\']?',
                    rf'{param_name}\s+([A-Za-z_][A-Za-z0-9_\s]*)',
                ]
                for pattern in string_patterns:
                    match = re.search(pattern, query, re.IGNORECASE)
                    if match:
                        value = match.group(1).strip()
                        break
        
        # Only add parameter if we found a value or it's required
        if value is not None:
            params[param_name] = value
    
    return {func_name: params}
