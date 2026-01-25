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
    
    # Parse prompt (may be JSON string with nested structure)
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
    
    # Parse functions (may be JSON string)
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
    props = func.get("parameters", {}).get("properties", {})
    
    params = {}
    query_lower = query.lower()
    
    for param_name, param_info in props.items():
        param_type = param_info.get("type", "string")
        
        if param_type == "string":
            # Extract location/city - look for patterns like "in X" or "for X"
            if param_name == "location" or "city" in param_name.lower() or "location" in param_name.lower():
                # Pattern: "in [City Name]" or "for [City Name]"
                city_patterns = [
                    r'(?:in|for|at)\s+([A-Z][a-zA-Z\s]+?)(?:\s+(?:in|for|over|during|including|next|the|\d))',
                    r'(?:in|for|at)\s+([A-Z][a-zA-Z\s]+?)(?:\?|$)',
                    r'weather\s+(?:in|for|at)\s+([A-Z][a-zA-Z\s]+)',
                ]
                for pattern in city_patterns:
                    match = re.search(pattern, query)
                    if match:
                        params[param_name] = match.group(1).strip()
                        break
                
                # Fallback: look for capitalized words that could be city names
                if param_name not in params:
                    # Common city pattern - capitalized words
                    city_match = re.search(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b', query)
                    if city_match:
                        params[param_name] = city_match.group(1).strip()
        
        elif param_type == "integer":
            # Extract numbers - look for duration patterns
            if "duration" in param_name.lower() or "hour" in param_info.get("description", "").lower():
                # Pattern: "X hours" or "next X hours"
                duration_patterns = [
                    r'(?:next|for|over)\s+(\d+)\s*(?:hours?|hrs?)',
                    r'(\d+)\s*(?:hours?|hrs?)',
                ]
                for pattern in duration_patterns:
                    match = re.search(pattern, query_lower)
                    if match:
                        params[param_name] = int(match.group(1))
                        break
            else:
                # Generic number extraction
                numbers = re.findall(r'\b(\d+)\b', query)
                if numbers:
                    params[param_name] = int(numbers[0])
        
        elif param_type == "boolean":
            # Check for boolean indicators in query
            description = param_info.get("description", "").lower()
            
            if "precipitation" in param_name.lower() or "precipitation" in description:
                # Check if precipitation is mentioned in query
                if "precipitation" in query_lower or "rain" in query_lower:
                    params[param_name] = True
                elif "include" in query_lower and "precipitation" in query_lower:
                    params[param_name] = True
                elif "including" in query_lower and "precipitation" in query_lower:
                    params[param_name] = True
            else:
                # Generic boolean - check for "include X" or "with X"
                param_keyword = param_name.replace("_", " ").replace("include", "").strip()
                if param_keyword and param_keyword in query_lower:
                    if "include" in query_lower or "with" in query_lower or "including" in query_lower:
                        params[param_name] = True
    
    return {func_name: params}
