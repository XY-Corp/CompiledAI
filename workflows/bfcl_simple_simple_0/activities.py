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
    """Extract function call parameters from natural language query.
    
    Parses the prompt to extract the function name and parameters,
    returning the result in the format {"function_name": {"param1": val1}}.
    Uses regex for number extraction - no LLM calls needed.
    """
    # Parse prompt - handle BFCL format (may be nested JSON)
    try:
        if isinstance(prompt, str):
            try:
                data = json.loads(prompt)
                # BFCL format: {"question": [[{"role": "user", "content": "..."}]]}
                if "question" in data and isinstance(data["question"], list):
                    if len(data["question"]) > 0 and isinstance(data["question"][0], list):
                        query = data["question"][0][0].get("content", prompt)
                    else:
                        query = str(data["question"])
                else:
                    query = str(data)
            except json.JSONDecodeError:
                query = prompt
        else:
            query = str(prompt)
    except Exception:
        query = str(prompt)

    # Parse functions list
    funcs = []
    if functions:
        if isinstance(functions, str):
            try:
                funcs = json.loads(functions)
            except json.JSONDecodeError:
                funcs = []
        else:
            funcs = functions
    
    # Get the target function schema
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    
    # Handle different parameter schema formats
    params_schema = func.get("parameters", {})
    if isinstance(params_schema, dict):
        props = params_schema.get("properties", {})
        required_params = params_schema.get("required", [])
    else:
        props = {}
        required_params = []

    # Extract parameters from query using regex
    params = {}
    
    # Extract all numbers from the query
    numbers = re.findall(r'\b(\d+(?:\.\d+)?)\b', query)
    number_idx = 0
    
    # Extract unit if mentioned (common patterns)
    unit_match = re.search(r'\b(units?|meters?|feet|inches?|cm|mm|kilometers?|miles?|yards?)\b', query, re.IGNORECASE)
    extracted_unit = unit_match.group(1) if unit_match else None
    
    # Map extracted values to parameter names based on schema
    for param_name, param_info in props.items():
        if isinstance(param_info, str):
            param_type = param_info
        else:
            param_type = param_info.get("type", "string")
        
        # Handle numeric parameters
        if param_type in ["integer", "number", "float"]:
            # Try to find contextual match first
            # Pattern: "param_name of X" or "param_name X" or "X param_name"
            context_patterns = [
                rf'{param_name}\s+(?:of\s+)?(\d+(?:\.\d+)?)',
                rf'(\d+(?:\.\d+)?)\s+(?:units?\s+)?{param_name}',
                rf'{param_name}\s*[:=]\s*(\d+(?:\.\d+)?)',
            ]
            
            found = False
            for pattern in context_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    value = match.group(1)
                    params[param_name] = int(value) if param_type == "integer" else float(value)
                    found = True
                    break
            
            # Fallback: use numbers in order
            if not found and number_idx < len(numbers):
                value = numbers[number_idx]
                params[param_name] = int(value) if param_type == "integer" else float(value)
                number_idx += 1
        
        # Handle string parameters (like unit)
        elif param_type == "string":
            if param_name == "unit" and extracted_unit:
                params[param_name] = extracted_unit
            else:
                # Try to extract string value contextually
                string_patterns = [
                    rf'{param_name}\s*[:=]\s*["\']?([^"\']+)["\']?',
                    rf'{param_name}\s+(?:is\s+)?["\']?([a-zA-Z_]+)["\']?',
                ]
                for pattern in string_patterns:
                    match = re.search(pattern, query, re.IGNORECASE)
                    if match:
                        params[param_name] = match.group(1).strip()
                        break

    # Only include required params and params we found values for
    # Don't include optional params without values
    final_params = {}
    for param_name in props.keys():
        if param_name in params:
            final_params[param_name] = params[param_name]
        elif param_name in required_params:
            # Required param missing - try harder or use default
            if props[param_name].get("type") in ["integer", "number", "float"]:
                if number_idx < len(numbers):
                    value = numbers[number_idx]
                    param_type = props[param_name].get("type", "integer")
                    final_params[param_name] = int(value) if param_type == "integer" else float(value)
                    number_idx += 1

    return {func_name: final_params}
