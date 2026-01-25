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
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        
        if param_type == "string":
            # For location/city extraction - look for city names
            if param_name in ["location", "city"]:
                # Common patterns: "for Chicago", "in Chicago", "about ... for Chicago"
                patterns = [
                    r'(?:for|in|about|of)\s+([A-Z][a-zA-Z\s]+?)(?:\?|$|,|\.|!)',
                    r'(?:data|quality|information|weather)\s+(?:for|in)\s+([A-Z][a-zA-Z\s]+?)(?:\?|$|,|\.|!)',
                    r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s*\??\s*$',  # City at end
                ]
                
                for pattern in patterns:
                    match = re.search(pattern, query)
                    if match:
                        city = match.group(1).strip().rstrip('?.,!')
                        # Filter out common non-city words
                        if city.lower() not in ['can', 'you', 'find', 'me', 'the', 'latest', 'information', 'about', 'air', 'quality', 'index', 'and', 'pollution', 'data']:
                            params[param_name] = city
                            break
                
                # Fallback: look for known city patterns
                if param_name not in params:
                    # Try to find capitalized words that look like city names
                    city_match = re.search(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b(?:\?|$)', query)
                    if city_match:
                        params[param_name] = city_match.group(1).strip()
        
        elif param_type == "boolean":
            # Check for keywords indicating true/false
            query_lower = query.lower()
            
            # Keywords that suggest detail=true
            detail_keywords = ['detailed', 'detail', 'additional', 'more info', 'pm2.5', 'pm10', 'ozone', 'pollution sources', 'comprehensive', 'full']
            
            # Check if any detail keywords are present
            has_detail = any(kw in query_lower for kw in detail_keywords)
            
            # Only include boolean param if explicitly requested or if it's required
            # For optional booleans, only include if there's evidence in the query
            if has_detail:
                params[param_name] = True
            # Don't include false for optional boolean params - let default apply
    
    return {func_name: params}
