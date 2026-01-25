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
    
    # Extract parameters based on schema
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
        
        # For species - check if mentioned, otherwise use default if not required
        if "species" in param_name.lower():
            # Look for species mentions in query
            species_patterns = [
                r'(?:in|for|of)\s+([A-Z][a-z]+\s+[a-z]+)',  # Scientific name like "Homo sapiens"
                r'(?:in|for|of)\s+(humans?|mice?|rats?|dogs?|cats?)',  # Common names
            ]
            
            species_found = None
            for pattern in species_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    species_found = match.group(1)
                    break
            
            # Only include if found or if required
            if species_found:
                params[param_name] = species_found
            # Don't include optional species param if not specified - let default apply
            continue
        
        # Generic string extraction for other params
        if param_type == "string" and param_name in required_params:
            # Try to extract any quoted strings or identifiers
            quoted_match = re.search(r'"([^"]+)"', query)
            if quoted_match:
                params[param_name] = quoted_match.group(1)
    
    return {func_name: params}
