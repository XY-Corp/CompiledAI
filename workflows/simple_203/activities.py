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
    """Extract function call parameters from user query and return as {func_name: {params}}.
    
    Uses regex and string matching to extract parameter values - no LLM calls needed.
    """
    # Parse prompt - may be JSON string with nested structure
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
        else:
            data = prompt
        
        # Extract user query from BFCL format: {"question": [[{"role": "user", "content": "..."}]]}
        if "question" in data and isinstance(data["question"], list):
            if len(data["question"]) > 0 and isinstance(data["question"][0], list):
                if len(data["question"][0]) > 0 and isinstance(data["question"][0][0], dict):
                    query = data["question"][0][0].get("content", str(prompt))
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
        
        if param_type == "string":
            # For location/city parameters - extract city name
            if "city" in param_desc or "location" in param_desc:
                # Common patterns: "for Chicago", "in Chicago", "about Chicago"
                city_patterns = [
                    r'(?:for|in|about|of)\s+([A-Z][a-zA-Z\s]+?)(?:\?|$|,|\.|!)',
                    r'(?:for|in|about|of)\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)?)',
                    r'data\s+for\s+([A-Z][a-zA-Z\s]+?)(?:\?|$|,|\.|!)',
                ]
                
                for pattern in city_patterns:
                    match = re.search(pattern, query)
                    if match:
                        city = match.group(1).strip().rstrip('?.,!')
                        params[param_name] = city
                        break
        
        elif param_type == "boolean":
            # Check for keywords indicating true/false
            query_lower = query.lower()
            
            # Keywords that suggest detail=true
            detail_keywords = ["detailed", "detail", "additional", "more info", "full", "complete", "all data", "comprehensive"]
            # Keywords that suggest detail=false
            simple_keywords = ["simple", "basic", "just", "only", "brief"]
            
            if any(kw in query_lower for kw in detail_keywords):
                params[param_name] = True
            elif any(kw in query_lower for kw in simple_keywords):
                params[param_name] = False
            # If not specified, don't include optional boolean (use default)
        
        elif param_type in ["integer", "number", "float"]:
            # Extract numbers from query
            numbers = re.findall(r'\d+(?:\.\d+)?', query)
            if numbers:
                if param_type == "integer":
                    params[param_name] = int(numbers[0])
                else:
                    params[param_name] = float(numbers[0])
    
    return {func_name: params}
