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
    """
    Extract function call parameters from natural language query.
    Returns format: {"function_name": {"param1": val1, ...}}
    """
    # Parse prompt - may be JSON string with nested structure
    try:
        if isinstance(prompt, str):
            try:
                data = json.loads(prompt)
                # Handle BFCL-style nested structure
                if "question" in data and isinstance(data["question"], list):
                    if len(data["question"]) > 0 and isinstance(data["question"][0], list):
                        query = data["question"][0][0].get("content", str(prompt))
                    else:
                        query = str(prompt)
                else:
                    query = data.get("content", str(prompt))
            except json.JSONDecodeError:
                query = prompt
        else:
            query = str(prompt)
    except Exception:
        query = str(prompt)

    # Parse functions - may be JSON string
    funcs = []
    if functions:
        if isinstance(functions, str):
            try:
                funcs = json.loads(functions)
            except json.JSONDecodeError:
                funcs = []
        else:
            funcs = functions
    
    # Get first function schema
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    
    # Get parameters schema - handle both "parameters" and nested "parameters.properties"
    params_schema = func.get("parameters", {})
    if "properties" in params_schema:
        props = params_schema.get("properties", {})
    else:
        props = params_schema
    
    required_params = params_schema.get("required", [])
    
    # Extract parameter values from query using regex
    params = {}
    
    for param_name, param_info in props.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_type in ["integer", "number", "float"]:
            # Extract numbers from query
            numbers = re.findall(r'\b(\d+(?:\.\d+)?)\b', query)
            if numbers:
                # Use first number found for numeric params
                if param_type == "integer":
                    params[param_name] = int(float(numbers[0]))
                else:
                    params[param_name] = float(numbers[0])
        
        elif param_type == "string":
            # Check for unit-related parameters
            if "unit" in param_name.lower() or "unit" in param_desc:
                # Common unit patterns
                unit_patterns = [
                    r'\b(\d+)\s*(inches?|inch|in)\b',
                    r'\b(\d+)\s*(centimeters?|cm)\b',
                    r'\b(\d+)\s*(meters?|m)\b',
                    r'\b(\d+)\s*(feet|foot|ft)\b',
                    r'\b(\d+)\s*(miles?|mi)\b',
                    r'\b(\d+)\s*(kilometers?|km)\b',
                    r'\b(\d+)\s*(millimeters?|mm)\b',
                ]
                
                for pattern in unit_patterns:
                    match = re.search(pattern, query, re.IGNORECASE)
                    if match:
                        unit_str = match.group(2).lower()
                        # Normalize unit names
                        if unit_str in ["inches", "inch", "in"]:
                            params[param_name] = "inches"
                        elif unit_str in ["centimeters", "centimeter", "cm"]:
                            params[param_name] = "cm"
                        elif unit_str in ["meters", "meter", "m"]:
                            params[param_name] = "m"
                        elif unit_str in ["feet", "foot", "ft"]:
                            params[param_name] = "feet"
                        elif unit_str in ["miles", "mile", "mi"]:
                            params[param_name] = "miles"
                        elif unit_str in ["kilometers", "kilometer", "km"]:
                            params[param_name] = "km"
                        elif unit_str in ["millimeters", "millimeter", "mm"]:
                            params[param_name] = "mm"
                        else:
                            params[param_name] = unit_str
                        break
            else:
                # Generic string extraction - look for quoted strings or named entities
                quoted = re.findall(r'"([^"]+)"', query)
                if quoted:
                    params[param_name] = quoted[0]
                else:
                    # Try to extract after common prepositions
                    match = re.search(r'(?:for|in|of|with|named?|called?)\s+([A-Za-z][A-Za-z\s]+?)(?:\s+(?:and|with|,|\.|\?|$))', query, re.IGNORECASE)
                    if match and param_name in required_params:
                        params[param_name] = match.group(1).strip()
    
    # Only include parameters that were extracted (don't add defaults unless required)
    return {func_name: params}
