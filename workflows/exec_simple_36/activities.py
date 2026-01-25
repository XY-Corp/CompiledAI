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
    """Extract function name and parameters from user query. Returns {"func_name": {params}}."""
    
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
                elif isinstance(first_item, dict):
                    query = first_item.get("content", str(prompt))
                else:
                    query = str(prompt)
            else:
                query = str(prompt)
        else:
            query = str(data) if not isinstance(data, str) else data
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
    
    # Get function details
    func = funcs[0] if isinstance(funcs, list) else funcs
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters based on schema
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_type == "string":
            # For city_name or location-related parameters
            if "city" in param_name.lower() or "city" in param_desc:
                # Try multiple patterns to extract city name
                city_patterns = [
                    r'coordinates?\s+(?:for|of)\s+([A-Za-z\s]+?)(?:\s+for|\s*\?|$)',
                    r'(?:for|in|to)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
                    r'trip\s+to\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
                    r'city\s+(?:of\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
                ]
                
                for pattern in city_patterns:
                    match = re.search(pattern, query, re.IGNORECASE)
                    if match:
                        city = match.group(1).strip()
                        # Clean up common trailing words
                        city = re.sub(r'\s+(for|to|and|with|me|they|the).*$', '', city, flags=re.IGNORECASE)
                        if city and len(city) > 1:
                            params[param_name] = city
                            break
                
                # Fallback: look for capitalized words that could be city names
                if param_name not in params:
                    # Find capitalized words (potential city names)
                    caps = re.findall(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b', query)
                    # Filter out common non-city words
                    non_cities = {'I', 'Could', 'They', 'The', 'Could', 'Can', 'Please', 'Would', 'My', 'Their'}
                    cities = [c for c in caps if c not in non_cities]
                    if cities:
                        params[param_name] = cities[0]
            
            # Generic string extraction
            elif param_name not in params:
                # Try to extract quoted strings first
                quoted = re.findall(r'"([^"]+)"|\'([^\']+)\'', query)
                if quoted:
                    params[param_name] = quoted[0][0] or quoted[0][1]
        
        elif param_type in ["integer", "number", "float"]:
            # Extract numbers
            numbers = re.findall(r'\b(\d+(?:\.\d+)?)\b', query)
            if numbers:
                if param_type == "integer":
                    params[param_name] = int(float(numbers[0]))
                else:
                    params[param_name] = float(numbers[0])
    
    return {func_name: params}
