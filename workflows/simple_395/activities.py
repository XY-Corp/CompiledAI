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
    """Extract function name and parameters from user query using regex and string matching."""
    
    # Parse prompt - may be JSON string with nested structure
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
        else:
            data = prompt
        
        # Extract user query from BFCL format: {"question": [[{"role": "user", "content": "..."}]]}
        if isinstance(data, dict) and "question" in data:
            question_data = data.get("question", [])
            if isinstance(question_data, list) and len(question_data) > 0:
                first_item = question_data[0]
                if isinstance(first_item, list) and len(first_item) > 0:
                    query = first_item[0].get("content", str(prompt))
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
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_name == "location":
            # Extract location - look for patterns like "of X" or "near X" or "in X"
            # Pattern: "of Central Park in New York" or "near Central Park, NY"
            location_patterns = [
                r'(?:of|near|at|from)\s+([A-Za-z\s]+(?:in|,)\s*[A-Za-z\s]+)',
                r'(?:of|near|at|from)\s+([A-Za-z\s]+)',
            ]
            
            for pattern in location_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    location = match.group(1).strip()
                    # Clean up - remove trailing words like "within"
                    location = re.sub(r'\s+within.*$', '', location, flags=re.IGNORECASE)
                    params[param_name] = location
                    break
        
        elif param_name == "radius":
            # Extract radius - look for number followed by "miles" or "mile"
            radius_patterns = [
                r'(\d+(?:\.\d+)?)\s*(?:miles?|mi)\b',
                r'within\s+(\d+(?:\.\d+)?)',
            ]
            
            for pattern in radius_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    radius_val = match.group(1)
                    # Convert to integer if param type is integer
                    if param_type == "integer":
                        params[param_name] = int(float(radius_val))
                    else:
                        params[param_name] = float(radius_val)
                    break
        
        elif param_name == "type":
            # Extract parking type - look for keywords
            type_keywords = ["public", "private", "street", "garage", "lot"]
            query_lower = query.lower()
            
            for keyword in type_keywords:
                if keyword in query_lower:
                    params[param_name] = keyword
                    break
            # Note: type is optional, so we don't set a default if not found
    
    return {func_name: params}
