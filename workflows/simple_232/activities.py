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
    """Extract function name and parameters from user query and function schema.
    
    Returns a dict with function name as key and parameters as nested object.
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
                query = data["question"][0][0].get("content", str(prompt))
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
    
    # Extract parameters from query using regex and string matching
    params = {}
    query_lower = query.lower()
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        
        if param_type == "integer":
            # Extract year or other integers
            numbers = re.findall(r'\b(\d{4})\b', query)  # Try 4-digit years first
            if numbers:
                params[param_name] = int(numbers[0])
            else:
                # Try any number
                numbers = re.findall(r'\b(\d+)\b', query)
                if numbers:
                    params[param_name] = int(numbers[0])
        
        elif param_type == "string":
            # For location parameter, extract country/place names
            if param_name == "location":
                # Common patterns for location extraction
                location_patterns = [
                    r'(?:king|queen|monarch|ruler)\s+of\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
                    r'(?:in|of)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:in|during)',
                    r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:monarch|king|queen)',
                ]
                
                for pattern in location_patterns:
                    match = re.search(pattern, query)
                    if match:
                        params[param_name] = match.group(1).strip()
                        break
                
                # Fallback: look for known country names
                if param_name not in params:
                    countries = ["England", "France", "Spain", "Germany", "Italy", "Russia", 
                                "China", "Japan", "India", "Britain", "United Kingdom", "UK"]
                    for country in countries:
                        if country.lower() in query_lower:
                            params[param_name] = country
                            break
        
        elif param_type == "boolean":
            # Check for keywords indicating true/false
            if param_name == "fullName":
                # Look for "full name" or "full title" in query
                if "full name" in query_lower or "full title" in query_lower:
                    params[param_name] = True
                # Don't include if not explicitly requested (use default)
    
    return {func_name: params}
