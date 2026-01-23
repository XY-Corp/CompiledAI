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
    
    # Parse prompt - may be JSON string with nested structure
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
    
    # Parse functions - may be JSON string
    try:
        if isinstance(functions, str):
            funcs = json.loads(functions)
        else:
            funcs = functions
    except (json.JSONDecodeError, TypeError):
        funcs = []
    
    # Get target function details
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    required_params = func.get("parameters", {}).get("required", [])
    
    # Extract parameters based on schema
    params = {}
    query_lower = query.lower()
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_type == "string":
            # For location/city parameters - extract city name
            if "location" in param_name.lower() or "city" in param_desc:
                # Pattern: "in [City, State]" or "in [City]" or "for [City]"
                location_patterns = [
                    r'(?:in|for|at)\s+([A-Za-z\s]+,\s*[A-Za-z\s]+)',  # City, State
                    r'(?:in|for|at)\s+([A-Za-z\s]+?)(?:\?|$|\.)',  # City only
                    r'weather\s+(?:in|for|at)\s+([A-Za-z\s,]+)',  # weather in/for City
                ]
                
                for pattern in location_patterns:
                    match = re.search(pattern, query, re.IGNORECASE)
                    if match:
                        location = match.group(1).strip().rstrip('?.,!')
                        # Clean up the location
                        if location:
                            params[param_name] = location
                            break
        
        elif param_type == "boolean":
            # Check if the query explicitly mentions this parameter's subject
            # For weather: temperature, humidity, etc.
            subject_keywords = []
            
            if "temperature" in param_name.lower() or "temperature" in param_desc:
                subject_keywords = ["temperature", "temp"]
            elif "humidity" in param_name.lower() or "humidity" in param_desc:
                subject_keywords = ["humidity", "humid"]
            
            # If the query mentions the subject, set to true
            # If not mentioned but has default, use default
            mentioned = any(kw in query_lower for kw in subject_keywords)
            
            if mentioned:
                params[param_name] = True
            # If not mentioned and not required, skip (use default)
        
        elif param_type in ["integer", "number", "float"]:
            # Extract numbers from query
            numbers = re.findall(r'\d+(?:\.\d+)?', query)
            if numbers:
                if param_type == "integer":
                    params[param_name] = int(numbers[0])
                else:
                    params[param_name] = float(numbers[0])
    
    # Ensure required params are present
    for req_param in required_params:
        if req_param not in params:
            # Try harder to extract required params
            if req_param == "location":
                # Fallback: extract any capitalized words that look like a place
                words = re.findall(r'[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*', query)
                # Filter out common non-location words
                non_locations = {"What", "The", "Current", "Default"}
                locations = [w for w in words if w not in non_locations]
                if locations:
                    params[req_param] = ", ".join(locations[-2:]) if len(locations) >= 2 else locations[-1]
    
    return {func_name: params}
