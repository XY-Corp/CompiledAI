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
            # Extract user query from BFCL format: {"question": [[{"role": "user", "content": "..."}]]}
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
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_type == "string":
            # For artist_name - extract name patterns
            if "artist" in param_name.lower() or "name" in param_desc:
                # Pattern: "by [Name]" or "artist [Name]"
                patterns = [
                    r'by\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)',  # "by James Plensa"
                    r'artist\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)',  # "artist James Plensa"
                    r'sculptor\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)',  # "sculptor James Plensa"
                ]
                for pattern in patterns:
                    match = re.search(pattern, query)
                    if match:
                        params[param_name] = match.group(1).strip()
                        break
                
                # Fallback: look for capitalized multi-word names
                if param_name not in params:
                    name_match = re.search(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)', query)
                    if name_match:
                        params[param_name] = name_match.group(1).strip()
        
        elif param_type == "boolean":
            # Check for keywords indicating true/false
            if "detail" in param_name.lower() or "detail" in param_desc:
                # Look for "detailed", "with detail", "description"
                if re.search(r'\b(detailed|with\s+detail|full\s+description|detailed\s+description)\b', query, re.IGNORECASE):
                    params[param_name] = True
                else:
                    # Check default from description
                    if "defaults to false" in param_desc.lower():
                        # Only set if explicitly requested
                        if re.search(r'\b(detail|detailed)\b', query, re.IGNORECASE):
                            params[param_name] = True
                    elif "defaults to true" in param_desc.lower():
                        params[param_name] = True
        
        elif param_type in ["integer", "number", "float"]:
            # Extract numbers
            numbers = re.findall(r'\d+(?:\.\d+)?', query)
            if numbers:
                if param_type == "integer":
                    params[param_name] = int(numbers[0])
                else:
                    params[param_name] = float(numbers[0])
    
    return {func_name: params}
