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
    """Extract function call parameters from user query using regex - NO LLM needed."""
    
    # Parse prompt - may be JSON string with nested structure
    try:
        if isinstance(prompt, str):
            try:
                data = json.loads(prompt)
                # Handle BFCL-style nested structure
                if "question" in data and isinstance(data["question"], list):
                    if len(data["question"]) > 0 and isinstance(data["question"][0], list):
                        query = data["question"][0][0].get("content", prompt)
                    else:
                        query = str(data["question"])
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
    
    # If no functions provided, try tools
    if not funcs and tools:
        if isinstance(tools, str):
            try:
                funcs = json.loads(tools)
            except json.JSONDecodeError:
                funcs = []
        else:
            funcs = tools
    
    if not funcs:
        return {"error": "No functions provided"}
    
    # Get the target function
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    
    # Handle different parameter schema formats
    params_schema = func.get("parameters", {})
    if isinstance(params_schema, dict):
        props = params_schema.get("properties", params_schema)
    else:
        props = {}
    
    # Extract parameters using regex - NO LLM NEEDED!
    params = {}
    
    # Extract all numbers from the query
    numbers = re.findall(r'(\d+(?:\.\d+)?)', query)
    
    # Extract unit if present (e.g., "cm", "m", "inches", etc.)
    unit_match = re.search(r'\b(\d+)\s*(cm|m|mm|inches|in|ft|feet|meters?)\b', query, re.IGNORECASE)
    unit = None
    if unit_match:
        unit = unit_match.group(2).lower()
        # Normalize unit
        if unit in ['meters', 'meter']:
            unit = 'm'
        elif unit in ['inches', 'in']:
            unit = 'inches'
        elif unit in ['feet', 'ft']:
            unit = 'ft'
    
    # Map extracted values to parameter names based on schema
    num_idx = 0
    for param_name, param_info in props.items():
        if isinstance(param_info, dict):
            param_type = param_info.get("type", "string")
        else:
            param_type = str(param_info)
        
        if param_type in ["integer", "int", "number", "float"]:
            if num_idx < len(numbers):
                if param_type in ["integer", "int"]:
                    params[param_name] = int(float(numbers[num_idx]))
                else:
                    params[param_name] = float(numbers[num_idx])
                num_idx += 1
        elif param_type == "string" and param_name == "unit":
            # For unit parameter, use extracted unit or default
            if unit:
                params[param_name] = unit
            # If unit is optional and we found one in the query, include it
            elif unit_match:
                params[param_name] = unit_match.group(2)
    
    # Return in the exact format requested: {"function_name": {params}}
    return {func_name: params}
