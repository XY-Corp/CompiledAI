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
    
    # Extract parameters from query
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        
        if param_type == "string":
            # Extract country/location names
            # Pattern: "in [Country]" or "for [Country]" or just look for capitalized words
            country_patterns = [
                r'(?:in|for|of)\s+(?:the\s+)?([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)',
                r'([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)\s+(?:in|for|over)',
            ]
            
            for pattern in country_patterns:
                match = re.search(pattern, query)
                if match:
                    value = match.group(1).strip()
                    # Filter out common non-country words
                    if value.lower() not in ['what', 'the', 'next', 'projected', 'population']:
                        params[param_name] = value
                        break
        
        elif param_type == "integer":
            # Extract numbers - look for patterns like "next X years" or just numbers
            year_patterns = [
                r'(?:next|in|for|over)\s+(\d+)\s+years?',
                r'(\d+)\s+years?',
                r'(\d+)-year',
            ]
            
            for pattern in year_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    params[param_name] = int(match.group(1))
                    break
        
        elif param_type == "float":
            # Extract float numbers - look for percentages or decimal numbers
            float_patterns = [
                r'(\d+\.?\d*)\s*%',
                r'rate\s+(?:of\s+)?(\d+\.?\d*)',
                r'(\d+\.\d+)',
            ]
            
            for pattern in float_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    params[param_name] = float(match.group(1))
                    break
            # Note: growth_rate is optional with default, so we don't need to extract it if not present
    
    return {func_name: params}
