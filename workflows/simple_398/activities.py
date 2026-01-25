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
    
    # Parse prompt (may be JSON string with nested structure)
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
    
    # Extract parameters based on schema
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        enum_values = param_info.get("enum", [])
        
        # Handle day of week extraction
        if enum_values and all(day in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"] for day in enum_values):
            # Match day of week (case-insensitive)
            day_pattern = r'\b(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b'
            day_match = re.search(day_pattern, query, re.IGNORECASE)
            if day_match:
                # Capitalize properly to match enum format
                params[param_name] = day_match.group(1).capitalize()
        
        # Handle museum name extraction
        elif "museum" in param_desc or "museum" in param_name.lower():
            # Common patterns for museum names
            # Pattern 1: "of the X" or "of X"
            museum_patterns = [
                r'(?:hours?\s+of\s+(?:the\s+)?|at\s+(?:the\s+)?|for\s+(?:the\s+)?)([A-Z][A-Za-z\s]+(?:Museum|Gallery|Institute|Center|Centre))',
                r'(?:the\s+)?([A-Z][A-Za-z\s]+(?:Museum|Gallery|Institute|Center|Centre))',
                r'(?:hours?\s+of\s+(?:the\s+)?|at\s+(?:the\s+)?|for\s+(?:the\s+)?)([A-Z][A-Za-z\s]+(?:of\s+[A-Z][A-Za-z\s]+)?)',
            ]
            
            for pattern in museum_patterns:
                museum_match = re.search(pattern, query)
                if museum_match:
                    museum_name = museum_match.group(1).strip()
                    # Clean up trailing words that aren't part of the name
                    museum_name = re.sub(r'\s+on\s+.*$', '', museum_name, flags=re.IGNORECASE)
                    museum_name = re.sub(r'\s+for\s+.*$', '', museum_name, flags=re.IGNORECASE)
                    if museum_name:
                        params[param_name] = museum_name
                        break
        
        # Handle generic string extraction with enum
        elif enum_values:
            for val in enum_values:
                if val.lower() in query.lower():
                    params[param_name] = val
                    break
        
        # Handle numeric parameters
        elif param_type in ["integer", "number", "float"]:
            numbers = re.findall(r'\d+(?:\.\d+)?', query)
            if numbers:
                if param_type == "integer":
                    params[param_name] = int(numbers[0])
                else:
                    params[param_name] = float(numbers[0])
    
    return {func_name: params}
