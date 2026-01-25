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
            # For country extraction - look for country names
            if "country" in param_name.lower() or "country" in param_desc:
                # Common patterns for country extraction
                # Pattern: "in [Country]" or "of [Country]" or "[Country]'s"
                country_patterns = [
                    r"(?:in|of|for|about)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)",  # "in Brazil", "of Brazil"
                    r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)'s\s+(?:situation|data|figures|numbers|cases|deaths)",  # "Brazil's situation"
                    r"focusing\s+on\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)",  # "focusing on Brazil"
                ]
                
                for pattern in country_patterns:
                    match = re.search(pattern, query)
                    if match:
                        country = match.group(1).strip()
                        # Filter out common non-country words
                        non_countries = {"COVID", "I", "Could", "The", "That", "This"}
                        if country not in non_countries:
                            params[param_name] = country
                            break
            else:
                # Generic string extraction - look for quoted strings or key phrases
                quoted_match = re.search(r'"([^"]+)"', query)
                if quoted_match:
                    params[param_name] = quoted_match.group(1)
        
        elif param_type in ["integer", "number", "float"]:
            # Extract numbers
            numbers = re.findall(r'\d+(?:\.\d+)?', query)
            if numbers:
                if param_type == "integer":
                    params[param_name] = int(numbers[0])
                else:
                    params[param_name] = float(numbers[0])
    
    return {func_name: params}
