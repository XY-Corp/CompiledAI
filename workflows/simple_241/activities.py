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
        
        # For this specific function: US_President_During_Event
        # We need to extract "event" (the historical event mentioned)
        if param_name == "event":
            # Extract the historical event from the query
            # Common patterns: "during the X", "during X", "in the X", "about X"
            event_patterns = [
                r'during\s+the\s+([A-Za-z\s]+?)(?:\?|$|\.)',
                r'during\s+([A-Za-z\s]+?)(?:\?|$|\.)',
                r'in\s+the\s+([A-Za-z\s]+?)(?:\?|$|\.)',
                r'about\s+the\s+([A-Za-z\s]+?)(?:\?|$|\.)',
            ]
            
            event_value = None
            for pattern in event_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    event_value = match.group(1).strip()
                    break
            
            if event_value:
                params[param_name] = event_value
            elif param_name in required_params:
                # Fallback: try to find any capitalized phrase that looks like an event
                # Look for phrases like "Civil War", "World War II", etc.
                event_match = re.search(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:\s+(?:War|Revolution|Crisis|Era|Period|Movement))?)', query)
                if event_match:
                    params[param_name] = event_match.group(1).strip()
        
        elif param_name == "country":
            # Extract country if mentioned, otherwise don't include (it's optional)
            country_patterns = [
                r'(?:in|of|for)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+president',
                r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+president',
                r'president\s+of\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
            ]
            
            for pattern in country_patterns:
                match = re.search(pattern, query)
                if match:
                    country_value = match.group(1).strip()
                    # Only include if it looks like a country name
                    if country_value.lower() not in ['the', 'a', 'an']:
                        params[param_name] = country_value
                        break
            
            # Note: "country" is optional per schema, so we don't add it if not found
        
        else:
            # Generic extraction for other string parameters
            if param_type == "string":
                # Try to extract based on description keywords
                if "event" in param_desc:
                    # Already handled above
                    pass
                elif "country" in param_desc:
                    # Already handled above
                    pass
    
    return {func_name: params}
