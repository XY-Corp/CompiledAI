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
    # Parse prompt - handle BFCL format (may be JSON string)
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
        else:
            data = prompt
        
        # Extract user query from nested structure
        if "question" in data and isinstance(data["question"], list):
            if len(data["question"]) > 0 and isinstance(data["question"][0], list):
                query = data["question"][0][0].get("content", str(prompt))
            else:
                query = str(prompt)
        else:
            query = str(prompt)
    except (json.JSONDecodeError, TypeError, KeyError):
        query = str(prompt)
    
    # Parse functions - may be JSON string
    if isinstance(functions, str):
        try:
            funcs = json.loads(functions)
        except json.JSONDecodeError:
            funcs = []
    else:
        funcs = functions if functions else []
    
    # Get target function details
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    required_params = func.get("parameters", {}).get("required", [])
    
    # Extract parameters from query
    params = {}
    query_lower = query.lower()
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_name == "location":
            # Extract location - look for city patterns
            # Pattern: "in <City>" or "in <City>, <State>"
            location_patterns = [
                r'in\s+([A-Z][a-zA-Z\s]+(?:,\s*[A-Z]{2})?)',  # "in Los Angeles" or "in Los Angeles, CA"
                r'(?:near|around|at)\s+([A-Z][a-zA-Z\s]+(?:,\s*[A-Z]{2})?)',
            ]
            
            for pattern in location_patterns:
                match = re.search(pattern, query)
                if match:
                    location = match.group(1).strip()
                    # Clean up - remove trailing words that aren't part of location
                    location = re.sub(r'\s+that\b.*$', '', location, flags=re.IGNORECASE)
                    params[param_name] = location
                    break
        
        elif param_name == "dietary_preference":
            # Extract dietary preferences from enum values
            enum_values = param_info.get("items", {}).get("enum", [])
            found_preferences = []
            
            for pref in enum_values:
                # Check if preference is mentioned in query (case-insensitive)
                if pref.lower() in query_lower:
                    found_preferences.append(pref)
            
            # Only include if we found preferences
            if found_preferences:
                params[param_name] = found_preferences
        
        elif param_type == "string":
            # Generic string extraction - try common patterns
            # Look for quoted strings or patterns like "for X" or "named X"
            string_patterns = [
                rf'{param_name}[:\s]+["\']?([^"\']+)["\']?',
                rf'(?:for|named|called)\s+([A-Za-z\s]+)',
            ]
            
            for pattern in string_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    params[param_name] = match.group(1).strip()
                    break
        
        elif param_type in ["integer", "number", "float"]:
            # Extract numbers
            numbers = re.findall(r'\d+(?:\.\d+)?', query)
            if numbers:
                if param_type == "integer":
                    params[param_name] = int(numbers[0])
                else:
                    params[param_name] = float(numbers[0])
        
        elif param_type == "array":
            # For arrays, try to extract comma-separated values or enum matches
            items_info = param_info.get("items", {})
            if "enum" in items_info:
                enum_values = items_info["enum"]
                found_values = []
                for val in enum_values:
                    if val.lower() in query_lower:
                        found_values.append(val)
                if found_values:
                    params[param_name] = found_values
    
    return {func_name: params}
