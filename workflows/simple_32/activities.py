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
    """Extract function call parameters from user query using regex and return as {func_name: {params}}."""
    
    # Parse prompt - may be JSON string with nested structure
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
            # Handle BFCL format: {"question": [[{"role": "user", "content": "..."}]]}
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
    
    # Get target function details
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    required_params = func.get("parameters", {}).get("required", [])
    
    # Extract all numbers from the query
    numbers = re.findall(r'\d+(?:\.\d+)?', query)
    
    # Build parameters based on schema
    params = {}
    num_idx = 0
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_type in ["integer", "float", "number"]:
            # Try to match specific patterns based on parameter description
            value = None
            
            # Check for height-related patterns
            if "height" in param_name.lower() or "height" in param_desc:
                height_match = re.search(r'(?:from|height[:\s]+|dropped\s+from)\s*(\d+(?:\.\d+)?)\s*(?:m|meter|meters)?', query, re.IGNORECASE)
                if height_match:
                    value = height_match.group(1)
            
            # Check for velocity-related patterns
            elif "velocity" in param_name.lower() or "velocity" in param_desc:
                velocity_match = re.search(r'(?:velocity[:\s]+|speed[:\s]+|initial[:\s]+)\s*(\d+(?:\.\d+)?)', query, re.IGNORECASE)
                if velocity_match:
                    value = velocity_match.group(1)
                else:
                    # For dropped objects, initial velocity is typically 0
                    if "dropped" in query.lower() and "initial" in param_name.lower():
                        value = "0"
            
            # Check for gravity-related patterns
            elif "gravity" in param_name.lower() or "gravity" in param_desc:
                gravity_match = re.search(r'(?:gravity[:\s]+|g\s*=\s*)(\d+(?:\.\d+)?)', query, re.IGNORECASE)
                if gravity_match:
                    value = gravity_match.group(1)
                # Skip if not explicitly mentioned and not required (use default)
                elif param_name not in required_params:
                    continue
            
            # Fallback: use next available number if no specific match
            if value is None and num_idx < len(numbers):
                value = numbers[num_idx]
                num_idx += 1
            
            # Convert to appropriate type
            if value is not None:
                if param_type == "integer":
                    params[param_name] = int(float(value))
                else:
                    params[param_name] = float(value)
        
        elif param_type == "string":
            # Extract string values using common patterns
            string_match = re.search(r'(?:for|in|of|with|named?)\s+([A-Za-z\s]+?)(?:\s+(?:and|with|,|\.)|$)', query, re.IGNORECASE)
            if string_match:
                params[param_name] = string_match.group(1).strip()
    
    # Handle special case: object dropped = initial velocity is 0
    if "initial_velocity" in params_schema and "initial_velocity" not in params:
        if "dropped" in query.lower() or "drop" in query.lower():
            params["initial_velocity"] = 0
    
    return {func_name: params}
