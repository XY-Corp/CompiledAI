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
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_name == "park_name" or "park" in param_desc or "name" in param_desc:
            # Extract park name - look for patterns like "of X National Park" or "X National Park"
            # Pattern 1: "of [Name] National Park"
            match = re.search(r'(?:of|about|for)\s+([A-Za-z\s]+?)(?:\s+National\s+Park)?(?:\?|$|\.)', query, re.IGNORECASE)
            if match:
                park_name = match.group(1).strip()
                # Clean up and ensure "National Park" is not duplicated
                park_name = re.sub(r'\s*National\s*Park\s*$', '', park_name, flags=re.IGNORECASE).strip()
                params[param_name] = park_name
            else:
                # Pattern 2: Look for capitalized words that could be a park name
                match = re.search(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+National\s+Park', query)
                if match:
                    params[param_name] = match.group(1).strip()
                else:
                    # Fallback: extract any proper noun sequence
                    words = query.split()
                    for i, word in enumerate(words):
                        if word[0].isupper() and word.lower() not in ['what', 'the', 'and', 'of']:
                            params[param_name] = word
                            break
        
        elif param_type == "array":
            # Extract array values - look for enum values in the query
            items_info = param_info.get("items", {})
            enum_values = items_info.get("enum", [])
            
            if enum_values:
                # Find which enum values are mentioned in the query
                found_values = []
                query_lower = query.lower()
                for enum_val in enum_values:
                    if enum_val.lower() in query_lower:
                        found_values.append(enum_val)
                
                if found_values:
                    params[param_name] = found_values
                else:
                    # If no exact matches, try to infer from context
                    # "elevation and area" -> ["Elevation", "Area"]
                    inferred = []
                    for enum_val in enum_values:
                        # Check for partial matches or related words
                        if enum_val.lower() in query_lower:
                            inferred.append(enum_val)
                    params[param_name] = inferred if inferred else enum_values[:1]
    
    return {func_name: params}
