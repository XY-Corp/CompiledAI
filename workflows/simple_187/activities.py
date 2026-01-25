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
    """Extract function name and parameters from user query. Returns {"func_name": {params}}."""
    
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
            # For location/city extraction
            if "city" in param_desc or "location" in param_desc:
                # Try patterns: "in <city>", "for <city>", "<city>, <state>"
                patterns = [
                    r'(?:in|for|at)\s+([A-Za-z\s]+(?:,\s*[A-Za-z\s]+)?)\??',
                    r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:,\s*[A-Z][a-z]+)?)',
                ]
                
                for pattern in patterns:
                    match = re.search(pattern, query)
                    if match:
                        location = match.group(1).strip().rstrip('?')
                        # Clean up common trailing words
                        location = re.sub(r'\s+(right now|today|currently|please).*$', '', location, flags=re.IGNORECASE)
                        if location:
                            params[param_name] = location
                            break
            else:
                # Generic string extraction
                numbers = re.findall(r'\d+', query)
                if numbers:
                    params[param_name] = numbers[0]
        
        elif param_type == "boolean":
            # Check if the query mentions what this boolean controls
            if "temperature" in param_desc.lower():
                # Check if temperature is mentioned in query
                if "temperature" in query_lower or "temp" in query_lower:
                    params[param_name] = True
            elif "humidity" in param_desc.lower():
                # Check if humidity is mentioned in query
                if "humidity" in query_lower:
                    params[param_name] = True
        
        elif param_type in ["integer", "number", "float"]:
            numbers = re.findall(r'\d+(?:\.\d+)?', query)
            if numbers:
                if param_type == "integer":
                    params[param_name] = int(numbers[0])
                else:
                    params[param_name] = float(numbers[0])
    
    return {func_name: params}
