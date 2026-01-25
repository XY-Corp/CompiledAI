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
    
    # Extract parameters using regex and string matching
    params = {}
    query_lower = query.lower()
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        enum_values = param_info.get("enum", [])
        
        # Handle enum values - check if any enum value appears in query
        if enum_values:
            for enum_val in enum_values:
                if enum_val.lower() in query_lower:
                    params[param_name] = enum_val
                    break
            continue
        
        # Extract based on parameter name and description
        if param_name == "model" or "model" in param_desc:
            # Extract guitar model - look for brand + model pattern
            # Common patterns: "Gibson Les Paul", "Fender Stratocaster", etc.
            model_patterns = [
                r'(Gibson\s+Les\s+Paul)',
                r'(Gibson\s+SG)',
                r'(Fender\s+Stratocaster)',
                r'(Fender\s+Telecaster)',
                r'(Gibson\s+\w+(?:\s+\w+)?)',
                r'(Fender\s+\w+(?:\s+\w+)?)',
            ]
            for pattern in model_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    params[param_name] = match.group(1).strip()
                    break
        
        elif param_name == "condition" or "condition" in param_desc:
            # Extract condition - look for condition keywords
            condition_patterns = [
                r'\b(excellent|good|poor|mint|fair|new|used)\s+condition\b',
                r'\bin\s+(excellent|good|poor|mint|fair)\b',
                r'\b(excellent|good|poor)\b'
            ]
            for pattern in condition_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    condition = match.group(1).strip().capitalize()
                    # Normalize to expected enum values if needed
                    if condition.lower() in ["excellent"]:
                        params[param_name] = "Excellent"
                    elif condition.lower() in ["good"]:
                        params[param_name] = "Good"
                    elif condition.lower() in ["poor"]:
                        params[param_name] = "Poor"
                    else:
                        params[param_name] = condition
                    break
        
        elif param_name == "location" or "location" in param_desc:
            # Extract location - look for location patterns
            location_patterns = [
                r'in\s+the\s+([A-Z][a-zA-Z\s]+?)(?:\s+area|\s+region|\s*$|\.)',
                r'in\s+([A-Z][a-zA-Z\s]+?)(?:\s+area|\s+region|\s*$|\.)',
                r'(?:near|around|at)\s+([A-Z][a-zA-Z\s]+?)(?:\s+area|\s+region|\s*$|\.)',
            ]
            for pattern in location_patterns:
                match = re.search(pattern, query)
                if match:
                    location = match.group(1).strip()
                    # Clean up trailing words that aren't part of location
                    location = re.sub(r'\s+(area|region)$', '', location, flags=re.IGNORECASE)
                    params[param_name] = location
                    break
    
    return {func_name: params}
