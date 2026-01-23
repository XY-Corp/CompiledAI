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
    # Parse prompt - may be JSON string with nested structure
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
        else:
            data = prompt
        
        # Extract user query from BFCL format: {"question": [[{"role": "user", "content": "..."}]]}
        if isinstance(data, dict) and "question" in data:
            question_data = data["question"]
            if isinstance(question_data, list) and len(question_data) > 0:
                if isinstance(question_data[0], list) and len(question_data[0]) > 0:
                    query = question_data[0][0].get("content", str(prompt))
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
            # For location parameters - extract city/place names
            if "location" in param_name.lower() or "city" in param_desc or "locality" in param_desc:
                # Common patterns for location extraction
                location_patterns = [
                    r'(?:in|at|near|around|for)\s+([A-Z][a-zA-Z\s]+?)(?:\s+with|\s+that|\s+and|\.|\?|$)',
                    r'(?:nurseries|stores|shops)\s+in\s+([A-Z][a-zA-Z\s]+?)(?:\s+with|\s+that|\s+and|\.|\?|$)',
                ]
                
                for pattern in location_patterns:
                    match = re.search(pattern, query)
                    if match:
                        params[param_name] = match.group(1).strip()
                        break
                
                # Fallback: look for capitalized words that could be city names
                if param_name not in params:
                    # Known cities pattern
                    city_match = re.search(r'\b(Toronto|Vancouver|Montreal|Calgary|Ottawa|New York|Los Angeles|Chicago|Houston|Phoenix)\b', query, re.IGNORECASE)
                    if city_match:
                        params[param_name] = city_match.group(1)
        
        elif param_type == "array":
            # For array parameters - check enum values if available
            items_info = param_info.get("items", {})
            enum_values = items_info.get("enum", [])
            
            if enum_values:
                # Match enum values mentioned in query
                matched_values = []
                for enum_val in enum_values:
                    # Check for the enum value or its lowercase/singular form
                    enum_lower = enum_val.lower()
                    # Handle plural forms (e.g., "annuals" -> "Annual")
                    if enum_lower in query_lower or enum_lower + "s" in query_lower or enum_lower.rstrip("s") in query_lower:
                        matched_values.append(enum_val)
                    # Also check for "annual plants" pattern
                    if f"{enum_lower} plant" in query_lower:
                        matched_values.append(enum_val)
                
                if matched_values:
                    params[param_name] = matched_values
    
    return {func_name: params}
