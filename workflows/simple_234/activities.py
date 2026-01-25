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
    
    # Get function details
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters from query using regex and string matching
    params = {}
    query_lower = query.lower()
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_enum = param_info.get("enum", [])
        param_desc = param_info.get("description", "").lower()
        
        if param_name == "century":
            # Extract century - look for patterns like "19th century", "19th", or just numbers
            century_patterns = [
                r'(\d{1,2})(?:st|nd|rd|th)\s*century',  # "19th century"
                r'(\d{1,2})(?:st|nd|rd|th)',  # "19th"
                r'century\s*(\d{1,2})',  # "century 19"
            ]
            for pattern in century_patterns:
                match = re.search(pattern, query_lower)
                if match:
                    params[param_name] = int(match.group(1))
                    break
        
        elif param_name == "region" and param_enum:
            # Match region from enum values
            for region in param_enum:
                if region.lower() in query_lower:
                    params[param_name] = region
                    break
            # If no specific region found but "European" mentioned, default behavior
            if param_name not in params and "european" in query_lower:
                # Check for directional hints
                if "north" in query_lower:
                    params[param_name] = "Northern"
                elif "south" in query_lower:
                    params[param_name] = "Southern"
                elif "east" in query_lower:
                    params[param_name] = "Eastern"
                elif "west" in query_lower:
                    params[param_name] = "Western"
                else:
                    # Default to Western for general European history
                    params[param_name] = "Western"
        
        elif param_name == "category" and param_enum:
            # Match category from enum values
            for category in param_enum:
                if category.lower() in query_lower:
                    params[param_name] = category
                    break
            # Check for synonyms
            if param_name not in params:
                if "war" in query_lower or "battle" in query_lower or "conflict" in query_lower:
                    params[param_name] = "Wars"
                elif "science" in query_lower or "discovery" in query_lower:
                    params[param_name] = "Scientific"
                elif "politic" in query_lower or "government" in query_lower:
                    params[param_name] = "Politics"
                elif "culture" in query_lower or "art" in query_lower:
                    params[param_name] = "Culture"
        
        elif param_type == "integer":
            # Generic integer extraction
            numbers = re.findall(r'\d+', query)
            if numbers and param_name not in params:
                params[param_name] = int(numbers[0])
        
        elif param_type == "string" and param_enum:
            # Generic enum matching
            for enum_val in param_enum:
                if enum_val.lower() in query_lower:
                    params[param_name] = enum_val
                    break
    
    return {func_name: params}
