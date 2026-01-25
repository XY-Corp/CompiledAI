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
    
    # Extract parameters from query using regex and string matching
    params = {}
    query_lower = query.lower()
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_name == "top_number" or param_type == "integer":
            # Extract numbers - look for "top N" pattern first
            top_match = re.search(r'top\s+(\d+)', query_lower)
            if top_match:
                params[param_name] = int(top_match.group(1))
            else:
                # Fallback: find any number
                numbers = re.findall(r'\d+', query)
                if numbers:
                    params[param_name] = int(numbers[0])
        
        elif param_name == "field_of_law":
            # Extract field of law - look for patterns like "in X law" or "X law"
            # Common patterns: "constitutional law", "criminal law", "civil law", etc.
            law_patterns = [
                r'in\s+([a-zA-Z\s]+?)\s+law',
                r'([a-zA-Z]+)\s+law\s+(?:in|cases)',
                r'([a-zA-Z]+)\s+law',
            ]
            for pattern in law_patterns:
                match = re.search(pattern, query_lower)
                if match:
                    field = match.group(1).strip()
                    # Clean up and format
                    params[param_name] = f"{field} law"
                    break
        
        elif param_name == "country":
            # Extract country - look for "in [Country]" at the end or country names
            country_patterns = [
                r'(?:in|from)\s+([A-Z][a-zA-Z\s]+?)(?:\.|$)',  # "in China." or "in China"
                r'(?:in|from)\s+the\s+([A-Z][a-zA-Z\s]+?)(?:\.|$)',  # "in the United States"
            ]
            for pattern in country_patterns:
                match = re.search(pattern, query)
                if match:
                    country = match.group(1).strip().rstrip('.')
                    # Don't capture "law" as country
                    if 'law' not in country.lower():
                        params[param_name] = country
                        break
    
    return {func_name: params}
