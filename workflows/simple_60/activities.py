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
            # Handle BFCL format: {"question": [[{"role": "user", "content": "..."}]]}
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
    required_params = func.get("parameters", {}).get("required", [])
    
    # Extract parameters from query
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        # For SNP ID - look for rs followed by numbers
        if "snp" in param_name.lower() or "snp" in param_desc:
            snp_match = re.search(r'rs\d+', query, re.IGNORECASE)
            if snp_match:
                params[param_name] = snp_match.group(0)
                continue
        
        # For species parameter - check if mentioned, otherwise use default
        if "species" in param_name.lower():
            # Look for species mentions in query
            species_patterns = [
                r'(?:in|for|of)\s+([A-Z][a-z]+\s+[a-z]+)',  # Scientific name like "Homo sapiens"
                r'(?:in|for|of)\s+(humans?|mice?|rats?|dogs?|cats?)',  # Common names
            ]
            for pattern in species_patterns:
                species_match = re.search(pattern, query, re.IGNORECASE)
                if species_match:
                    params[param_name] = species_match.group(1)
                    break
            # Don't include optional param if not found - let default apply
            continue
        
        # For generic string parameters - try to extract relevant text
        if param_type == "string" and param_name in required_params:
            # Try to find quoted strings
            quoted_match = re.search(r'"([^"]+)"', query)
            if quoted_match:
                params[param_name] = quoted_match.group(1)
                continue
            
            # Try to find IDs (alphanumeric with possible prefixes)
            id_match = re.search(r'\b([a-zA-Z]{1,3}\d+)\b', query)
            if id_match:
                params[param_name] = id_match.group(1)
                continue
    
    return {func_name: params}
