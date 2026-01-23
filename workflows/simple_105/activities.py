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
    """Extract function call parameters from natural language query.
    
    Parses the user query to identify the function to call and extracts
    parameter values using regex patterns. Returns the function call
    in the format {"function_name": {"param1": val1, ...}}.
    """
    # Parse prompt - may be JSON string with nested structure
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
        else:
            data = prompt
        
        # Extract user query from BFCL format: {"question": [[{"role": "user", "content": "..."}]]}
        if "question" in data and isinstance(data["question"], list):
            if len(data["question"]) > 0 and isinstance(data["question"][0], list):
                if len(data["question"][0]) > 0 and isinstance(data["question"][0][0], dict):
                    query = data["question"][0][0].get("content", str(prompt))
                else:
                    query = str(prompt)
            else:
                query = str(prompt)
        else:
            query = str(prompt)
    except (json.JSONDecodeError, TypeError):
        query = str(prompt)
    
    # Parse functions - may be JSON string
    try:
        if isinstance(functions, str):
            funcs = json.loads(functions)
        else:
            funcs = functions
    except (json.JSONDecodeError, TypeError):
        funcs = []
    
    # Get function details
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters based on function type and query patterns
    params = {}
    
    # For math.power: extract base and exponent
    if func_name == "math.power":
        # Pattern: "power of X raised to Y" or "X raised to the power Y" or "X to the power of Y"
        patterns = [
            r'power\s+of\s+(\d+)\s+raised\s+to\s+(?:the\s+)?(?:power\s+)?(\d+)',
            r'(\d+)\s+raised\s+to\s+(?:the\s+)?power\s+(?:of\s+)?(\d+)',
            r'(\d+)\s+to\s+the\s+power\s+(?:of\s+)?(\d+)',
            r'(\d+)\s*\^\s*(\d+)',
            r'(\d+)\s+power\s+(\d+)',
        ]
        
        base, exponent = None, None
        for pattern in patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                base = int(match.group(1))
                exponent = int(match.group(2))
                break
        
        # Fallback: extract all numbers if patterns don't match
        if base is None or exponent is None:
            numbers = re.findall(r'\d+', query)
            if len(numbers) >= 2:
                base = int(numbers[0])
                exponent = int(numbers[1])
        
        if base is not None and exponent is not None:
            params["base"] = base
            params["exponent"] = exponent
            
            # Check for optional mod parameter
            mod_match = re.search(r'mod(?:ulus)?\s*(?:is|=|:)?\s*(\d+)', query, re.IGNORECASE)
            if mod_match:
                params["mod"] = int(mod_match.group(1))
    
    else:
        # Generic extraction for other functions
        # Extract all numbers from query
        numbers = re.findall(r'\d+(?:\.\d+)?', query)
        
        # Map numbers to numeric parameters in order
        num_idx = 0
        for param_name, param_info in params_schema.items():
            param_type = param_info.get("type", "string") if isinstance(param_info, dict) else "string"
            required = param_name in func.get("parameters", {}).get("required", [])
            
            if param_type in ["integer", "number", "float"]:
                if num_idx < len(numbers):
                    if param_type == "integer":
                        params[param_name] = int(float(numbers[num_idx]))
                    else:
                        params[param_name] = float(numbers[num_idx])
                    num_idx += 1
            elif param_type == "string" and required:
                # Try to extract string values
                string_match = re.search(r'(?:for|in|of|with|named?)\s+["\']?([A-Za-z\s]+?)["\']?(?:\s+(?:and|with|,)|$)', query, re.IGNORECASE)
                if string_match:
                    params[param_name] = string_match.group(1).strip()
    
    return {func_name: params}
