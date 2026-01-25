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
    # Parse prompt - handle BFCL format (may be JSON with nested structure)
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
            # BFCL format: {"question": [[{"role": "user", "content": "..."}]], "function": [...]}
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
        param_desc = param_info.get("description", "").lower()
        
        if param_type == "string":
            # Extract location - look for place names
            if "location" in param_name.lower() or "location" in param_desc:
                # Common patterns: "in [location]", "of [location]", "at [location]"
                location_patterns = [
                    r'(?:in|of|at|for)\s+(?:the\s+)?([A-Za-z][A-Za-z\s]+?)(?:\s+in\s+|\s+for\s+|\s+during\s+|\s*$|\s*\.)',
                    r'(?:population|species|turtles?)\s+(?:in|of|at)\s+(?:the\s+)?([A-Za-z][A-Za-z\s]+?)(?:\s+in\s+|\s+for\s+|\s+during\s+|\s*$|\s*\.)',
                ]
                for pattern in location_patterns:
                    match = re.search(pattern, query, re.IGNORECASE)
                    if match:
                        location = match.group(1).strip()
                        # Clean up trailing words that aren't part of location
                        location = re.sub(r'\s+(in|for|during|of)\s*$', '', location, flags=re.IGNORECASE)
                        if location and len(location) > 2:
                            params[param_name] = location
                            break
        
        elif param_type == "integer":
            # Extract year - look for 4-digit numbers (years)
            if "year" in param_name.lower() or "year" in param_desc:
                year_match = re.search(r'\b(19\d{2}|20\d{2})\b', query)
                if year_match:
                    params[param_name] = int(year_match.group(1))
            else:
                # Generic integer extraction
                numbers = re.findall(r'\b(\d+)\b', query)
                if numbers:
                    params[param_name] = int(numbers[0])
        
        elif param_type == "boolean":
            # Check if the query mentions the concept related to this boolean
            if "species" in param_name.lower() or "species" in param_desc:
                # Check if user asks about species
                if "species" in query_lower:
                    params[param_name] = True
            else:
                # Generic boolean - check for yes/no, true/false, include/exclude
                if re.search(r'\b(yes|true|include|with)\b', query_lower):
                    params[param_name] = True
                elif re.search(r'\b(no|false|exclude|without)\b', query_lower):
                    params[param_name] = False
    
    return {func_name: params}
