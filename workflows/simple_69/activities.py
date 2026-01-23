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
    """Extract function name and parameters from user query. Returns {func_name: {params}}."""
    
    # Parse prompt - may be JSON string with nested structure
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
            # Handle BFCL format: {"question": [[{"role": "user", "content": "..."}]], "function": [...]}
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
    
    # Extract parameters from query using regex and string matching
    params = {}
    query_lower = query.lower()
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        
        if param_type == "string":
            # For location: look for place names
            if param_name == "location":
                # Common patterns: "in [location]", "of [location]", "at [location]"
                location_patterns = [
                    r'in\s+([A-Za-z][A-Za-z\s]+?)(?:\s+in\s+|\s+at\s+|\s+during\s+|\s+for\s+|\.|$)',
                    r'of\s+turtles\s+in\s+([A-Za-z][A-Za-z\s]+?)(?:\s+in\s+|\s+at\s+|\s+during\s+|\s+for\s+|\.|$)',
                    r'population.*?in\s+([A-Za-z][A-Za-z\s]+?)(?:\s+in\s+|\s+at\s+|\s+during\s+|\s+for\s+|\.|$)',
                ]
                for pattern in location_patterns:
                    match = re.search(pattern, query, re.IGNORECASE)
                    if match:
                        location = match.group(1).strip()
                        # Clean up - remove trailing words like "in", "at", years
                        location = re.sub(r'\s+\d{4}.*$', '', location).strip()
                        if location and len(location) > 1:
                            params[param_name] = location
                            break
        
        elif param_type == "integer":
            # For year: look for 4-digit numbers (years)
            if param_name == "year":
                year_match = re.search(r'\b(19\d{2}|20\d{2})\b', query)
                if year_match:
                    params[param_name] = int(year_match.group(1))
        
        elif param_type == "boolean":
            # For species: check if "species" is mentioned in the query
            if param_name == "species":
                if "species" in query_lower:
                    params[param_name] = True
    
    return {func_name: params}
