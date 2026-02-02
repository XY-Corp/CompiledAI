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
    """Extract function call parameters from user query and return as {func_name: {params}}.
    
    Uses regex and string parsing to extract values - NO LLM calls needed.
    """
    # Step 1: Parse prompt to extract user query
    try:
        if isinstance(prompt, str):
            try:
                data = json.loads(prompt)
                # Handle BFCL nested format: {"question": [[{"content": "..."}]]}
                if "question" in data and isinstance(data["question"], list):
                    if len(data["question"]) > 0 and isinstance(data["question"][0], list):
                        if len(data["question"][0]) > 0:
                            query = data["question"][0][0].get("content", prompt)
                        else:
                            query = prompt
                    else:
                        query = prompt
                else:
                    query = prompt
            except json.JSONDecodeError:
                query = prompt
        else:
            query = str(prompt)
    except Exception:
        query = str(prompt)

    # Step 2: Parse functions list
    funcs = []
    if functions:
        if isinstance(functions, str):
            try:
                funcs = json.loads(functions)
            except json.JSONDecodeError:
                funcs = []
        else:
            funcs = functions
    
    # Fallback to tools if functions is empty
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

    # Step 3: Get target function details
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    
    # Handle different schema formats for parameters
    params_schema = func.get("parameters", {})
    if isinstance(params_schema, dict):
        props = params_schema.get("properties", {})
        required_params = params_schema.get("required", [])
    else:
        props = {}
        required_params = []

    # Step 4: Extract parameter values using regex
    params = {}
    query_lower = query.lower()

    for param_name, param_info in props.items():
        param_type = param_info.get("type", "string") if isinstance(param_info, dict) else "string"
        
        if param_type in ["integer", "number", "float"]:
            # Extract numbers from query
            # Try specific patterns first: "radius of X", "X radius", etc.
            patterns = [
                rf'{param_name}\s+(?:of\s+)?(\d+(?:\.\d+)?)',  # "radius of 10" or "radius 10"
                rf'(\d+(?:\.\d+)?)\s+{param_name}',  # "10 radius"
                rf'(?:of|with|=)\s*(\d+(?:\.\d+)?)',  # "of 10", "with 10", "= 10"
                rf'(\d+(?:\.\d+)?)',  # fallback: any number
            ]
            
            for pattern in patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    value = match.group(1)
                    if param_type == "integer":
                        params[param_name] = int(float(value))
                    else:
                        params[param_name] = float(value)
                    break
        
        elif param_type == "string":
            # Extract string values - look for quoted strings or specific patterns
            # Check for units specifically
            if param_name == "units":
                unit_patterns = [
                    r'(?:in|using)\s+(meters?|feet|inches|centimeters?|cm|m|ft|in)',
                    r'(meters?|feet|inches|centimeters?|cm|m|ft|in)\s+(?:units?)?',
                ]
                for pattern in unit_patterns:
                    match = re.search(pattern, query, re.IGNORECASE)
                    if match:
                        params[param_name] = match.group(1).lower()
                        break
            else:
                # Generic string extraction - look for quoted values
                quoted_match = re.search(r'["\']([^"\']+)["\']', query)
                if quoted_match:
                    params[param_name] = quoted_match.group(1)

    # Only include required params and params we found values for
    # Don't include optional params without values
    final_params = {}
    for param_name in props.keys():
        if param_name in params:
            final_params[param_name] = params[param_name]
        elif param_name in required_params:
            # Required param not found - try harder with fallback
            param_info = props[param_name]
            param_type = param_info.get("type", "string") if isinstance(param_info, dict) else "string"
            if param_type in ["integer", "number", "float"]:
                # Get all numbers from query
                all_numbers = re.findall(r'\d+(?:\.\d+)?', query)
                if all_numbers:
                    value = all_numbers[0]
                    if param_type == "integer":
                        final_params[param_name] = int(float(value))
                    else:
                        final_params[param_name] = float(value)

    return {func_name: final_params}
