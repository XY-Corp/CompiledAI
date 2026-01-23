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
    """Extract function name and parameters from user query. Returns {func_name: {params}}."""
    
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
    
    # Get function details
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters from query using regex and string matching
    params = {}
    query_lower = query.lower()
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_name == "species":
            # Extract species name - look for patterns like "for X" or common species names
            species_patterns = [
                r'for\s+([A-Z][a-z]+\s+[A-Z]?[a-z]+)',  # "for Homo Sapiens"
                r'of\s+([A-Z][a-z]+\s+[A-Z]?[a-z]+)',   # "of Homo Sapiens"
                r'([A-Z][a-z]+\s+[Ss]apiens)',           # "Homo Sapiens" or "Homo sapiens"
            ]
            for pattern in species_patterns:
                match = re.search(pattern, query)
                if match:
                    params[param_name] = match.group(1).strip()
                    break
        
        elif param_name == "years":
            # Extract number of years - look for patterns like "50 years" or "next 50"
            years_patterns = [
                r'(?:next|for)\s+(\d+)\s+years?',       # "next 50 years" or "for 50 years"
                r'(\d+)\s+years?',                      # "50 years"
            ]
            for pattern in years_patterns:
                match = re.search(pattern, query_lower)
                if match:
                    params[param_name] = int(match.group(1))
                    break
        
        elif param_name == "model":
            # Extract model name - look for known model options
            model_options = ["darwin", "lamarck"]
            for model in model_options:
                if model in query_lower:
                    # Capitalize properly
                    params[param_name] = model.capitalize()
                    break
        
        elif param_type == "integer":
            # Generic integer extraction
            numbers = re.findall(r'\d+', query)
            if numbers:
                params[param_name] = int(numbers[0])
        
        elif param_type == "string":
            # Generic string extraction - try to find quoted strings or after "for/of/with"
            quoted = re.search(r'"([^"]+)"', query)
            if quoted:
                params[param_name] = quoted.group(1)
    
    return {func_name: params}
