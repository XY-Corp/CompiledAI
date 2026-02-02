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
    Extract function call parameters from user query.
    Returns format: {"function_name": {"param1": val1, "param2": val2}}
    """
    # Step 1: Parse prompt - handle BFCL nested JSON format
    query = prompt
    if isinstance(prompt, str):
        try:
            data = json.loads(prompt)
            # BFCL format: {"question": [[{"role": "user", "content": "..."}]]}
            if "question" in data and isinstance(data["question"], list):
                if len(data["question"]) > 0 and isinstance(data["question"][0], list):
                    if len(data["question"][0]) > 0:
                        query = data["question"][0][0].get("content", prompt)
        except (json.JSONDecodeError, TypeError, KeyError):
            query = prompt
    
    # Step 2: Parse functions list
    funcs = functions
    if isinstance(functions, str):
        try:
            funcs = json.loads(functions)
        except json.JSONDecodeError:
            funcs = []
    
    if not funcs:
        funcs = []
    
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    required_params = func.get("parameters", {}).get("required", [])
    
    # Step 3: Extract parameter values using regex
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_type == "integer":
            # Extract integers from query
            numbers = re.findall(r'\b(\d+)\b', query)
            if numbers:
                # Use the first number found for integer params
                params[param_name] = int(numbers[0])
        
        elif param_type == "boolean":
            # Check for explicit boolean indicators in query
            query_lower = query.lower()
            
            # Check for explicit false indicators
            if any(word in query_lower for word in ["not formatted", "as array", "unformatted", "raw"]):
                params[param_name] = False
            # Check for explicit true indicators
            elif any(word in query_lower for word in ["formatted", "as string"]):
                params[param_name] = True
            else:
                # Check description for default value hint
                if "default is true" in param_desc or "default true" in param_desc:
                    params[param_name] = True
                elif "default is false" in param_desc or "default false" in param_desc:
                    params[param_name] = False
                else:
                    # Default to true for formatted-type params
                    params[param_name] = True
        
        elif param_type == "string":
            # Try to extract string values based on common patterns
            # Pattern: "for X" or "of X" or quoted strings
            string_patterns = [
                r'"([^"]+)"',  # Quoted strings
                r"'([^']+)'",  # Single quoted strings
                r'(?:for|of|named?|called?)\s+([A-Za-z0-9_\s]+?)(?:\s*[,.]|$)',
            ]
            
            for pattern in string_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    params[param_name] = match.group(1).strip()
                    break
        
        elif param_type == "number" or param_type == "float":
            # Extract float/decimal numbers
            numbers = re.findall(r'\b(\d+(?:\.\d+)?)\b', query)
            if numbers:
                params[param_name] = float(numbers[0])
    
    return {func_name: params}
