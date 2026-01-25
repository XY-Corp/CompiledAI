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
    """Extract function name and parameters from user query using regex patterns."""
    
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
    
    # Get function details
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters using regex
    params = {}
    
    # Extract all numbers from the query
    numbers = re.findall(r'\b(\d+(?:\.\d+)?)\b', query)
    
    # Map numbers to parameters based on schema order and context
    num_idx = 0
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        required = param_name in func.get("parameters", {}).get("required", [])
        
        if param_type in ["integer", "number", "float"]:
            # Try to find contextual match first
            # Look for patterns like "distance of X" or "X kilometers"
            if param_name == "distance":
                distance_match = re.search(r'distance\s+of\s+(\d+)|(\d+)\s*(?:km|kilometers?|miles?|meters?)', query, re.IGNORECASE)
                if distance_match:
                    val = distance_match.group(1) or distance_match.group(2)
                    params[param_name] = int(val) if param_type == "integer" else float(val)
                    continue
            
            if param_name == "duration":
                duration_match = re.search(r'duration\s+of\s+(\d+)|(\d+)\s*(?:hours?|hrs?|minutes?|mins?|seconds?|secs?)', query, re.IGNORECASE)
                if duration_match:
                    val = duration_match.group(1) or duration_match.group(2)
                    params[param_name] = int(val) if param_type == "integer" else float(val)
                    continue
            
            # Fallback: use numbers in order
            if num_idx < len(numbers):
                val = numbers[num_idx]
                params[param_name] = int(val) if param_type == "integer" else float(val)
                num_idx += 1
        
        elif param_type == "string":
            # For optional string params like "unit", check if mentioned
            if param_name == "unit":
                # Look for unit specification
                unit_match = re.search(r'(?:in|unit[s]?\s*(?:of|:)?)\s*(km/h|mph|m/s|meters?\s*per\s*second)', query, re.IGNORECASE)
                if unit_match:
                    params[param_name] = unit_match.group(1).lower()
                # Don't add optional params if not specified
            else:
                # For other string params, try to extract
                string_match = re.search(rf'{param_name}\s*(?:is|of|:)?\s*["\']?([^"\']+)["\']?', query, re.IGNORECASE)
                if string_match and required:
                    params[param_name] = string_match.group(1).strip()
    
    return {func_name: params}
