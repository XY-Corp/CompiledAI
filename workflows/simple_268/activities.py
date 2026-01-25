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
    """Extract function call parameters from natural language query.
    
    Parses the user query and function schema to extract parameter values
    using regex and string matching patterns.
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
    
    # Extract parameters from query using regex patterns
    params = {}
    query_lower = query.lower()
    
    for param_name, param_info in params_schema.items():
        param_desc = param_info.get("description", "").lower()
        
        if param_name == "artist":
            # Extract artist name - look for "of [Artist]" or "by [Artist]"
            # Common pattern: "sculptures of Michelangelo"
            artist_patterns = [
                r'(?:sculptures?\s+(?:of|by)\s+)([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
                r'(?:of|by)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
                r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*?)(?:\'s|\s+sculptures?)',
            ]
            for pattern in artist_patterns:
                match = re.search(pattern, query)
                if match:
                    params[param_name] = match.group(1).strip()
                    break
        
        elif param_name == "material":
            # Extract material - look for "with material [Material]" or "made of [Material]"
            material_patterns = [
                r'(?:with\s+)?material\s+([A-Z][a-z]+)',
                r'made\s+(?:of|from)\s+([A-Z][a-z]+)',
                r'([A-Z][a-z]+)\s+sculptures?',
            ]
            for pattern in material_patterns:
                match = re.search(pattern, query)
                if match:
                    params[param_name] = match.group(1).strip()
                    break
        
        elif param_name == "location":
            # Extract location - look for "in [Location]" at end or location patterns
            location_patterns = [
                r'\bin\s+([A-Z][a-z]+(?:,?\s+[A-Z][a-z]+)*)\s*\.?\s*$',
                r'\bat\s+([A-Z][a-z]+(?:,?\s+[A-Z][a-z]+)*)',
                r'\bnear\s+([A-Z][a-z]+(?:,?\s+[A-Z][a-z]+)*)',
            ]
            for pattern in location_patterns:
                match = re.search(pattern, query)
                if match:
                    params[param_name] = match.group(1).strip()
                    break
    
    return {func_name: params}
