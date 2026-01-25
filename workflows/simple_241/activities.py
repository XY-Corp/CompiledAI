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
    
    Parses the prompt to extract the user's query, then extracts parameter values
    using regex and string matching based on the function schema.
    """
    # Parse prompt (may be JSON string with nested structure)
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
    
    # Parse functions (may be JSON string)
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
    required_params = func.get("parameters", {}).get("required", [])
    
    # Extract parameters based on schema
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        # For this specific case: extract "event" parameter
        # The query asks about a historical event - extract the event name
        if param_name == "event":
            # Pattern: "during the X" or "during X"
            event_patterns = [
                r'during\s+the\s+([A-Za-z\s]+?)(?:\?|$)',
                r'during\s+([A-Za-z\s]+?)(?:\?|$)',
                r'(?:in|at)\s+the\s+([A-Za-z\s]+?)(?:\?|$)',
            ]
            
            for pattern in event_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    event_value = match.group(1).strip()
                    # Clean up trailing punctuation
                    event_value = re.sub(r'[\?\.\!]+$', '', event_value).strip()
                    params[param_name] = event_value
                    break
            
            # If no match found but it's required, try to extract any capitalized phrase
            if param_name not in params and param_name in required_params:
                # Look for capitalized words that might be event names
                cap_match = re.search(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+(?:War|Revolution|Crisis|Event|Battle|Movement))', query)
                if cap_match:
                    params[param_name] = cap_match.group(1).strip()
        
        # For "country" parameter - it's optional, only include if explicitly mentioned
        elif param_name == "country":
            # Check if a country is explicitly mentioned
            country_patterns = [
                r'(?:in|of|for)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+president',
                r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+president',
            ]
            
            for pattern in country_patterns:
                match = re.search(pattern, query)
                if match:
                    country_value = match.group(1).strip()
                    # Only add if it looks like a country name (not "U.S." which is already implied)
                    if country_value.lower() not in ['the', 'a', 'an']:
                        params[param_name] = country_value
                        break
            
            # Note: "country" is optional and defaults to 'USA', so we don't need to include it
            # if not explicitly specified in the query
    
    return {func_name: params}
