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
    """Extract function name and parameters from user query based on function schema.
    
    Returns format: {"function_name": {"param1": val1, "param2": val2}}
    """
    # Parse prompt - handle BFCL format (may be JSON with nested structure)
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
            # BFCL format: {"question": [[{"role": "user", "content": "..."}]], "function": [...]}
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

    if not funcs:
        return {"error": "No functions provided"}

    func = funcs[0]
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters based on schema
    params = {}
    query_lower = query.lower()
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_type == "string":
            # Location extraction - look for city names
            if "location" in param_name.lower() or "city" in param_desc or "locality" in param_desc:
                # Common patterns for location extraction
                # Pattern: "in [City]" or "near [City]" or "around [City]"
                location_patterns = [
                    r'\bin\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)',  # "in Toronto"
                    r'\bnear\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)',  # "near Toronto"
                    r'\baround\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)',  # "around Toronto"
                    r'\bat\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)',  # "at Toronto"
                ]
                
                for pattern in location_patterns:
                    match = re.search(pattern, query)
                    if match:
                        params[param_name] = match.group(1).strip()
                        break
                        
        elif param_type == "array":
            # Handle array parameters - check for enum values
            items_info = param_info.get("items", {})
            enum_values = items_info.get("enum", [])
            
            if enum_values:
                # Check which enum values are mentioned in the query
                matched_values = []
                for enum_val in enum_values:
                    # Check for the enum value in query (case-insensitive)
                    if enum_val.lower() in query_lower:
                        matched_values.append(enum_val)
                
                if matched_values:
                    params[param_name] = matched_values
                    
        elif param_type in ["integer", "number", "float"]:
            # Extract numbers
            numbers = re.findall(r'\d+(?:\.\d+)?', query)
            if numbers:
                if param_type == "integer":
                    params[param_name] = int(numbers[0])
                else:
                    params[param_name] = float(numbers[0])

    return {func_name: params}
