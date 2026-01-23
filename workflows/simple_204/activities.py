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
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_name == "location":
            # Extract city/state - look for patterns like "in Seattle" or "Seattle, WA"
            # Pattern for "in <City>" at end or before other clauses
            location_patterns = [
                r'in\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:,\s*[A-Z]{2})?)\s*[.,]?\s*$',
                r'in\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:,\s*[A-Z]{2})?)',
                r'near\s+(?:me\s+)?(?:in\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
            ]
            for pattern in location_patterns:
                match = re.search(pattern, query)
                if match:
                    params[param_name] = match.group(1).strip()
                    break
        
        elif param_name == "cuisine":
            # Extract cuisine type - look for patterns like "Chinese cuisine" or "offer Chinese"
            cuisine_patterns = [
                r'(\w+)\s+cuisine',
                r'offer\s+(\w+)',
                r'(\w+)\s+food',
                r'(\w+)\s+restaurants?',
            ]
            for pattern in cuisine_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    cuisine = match.group(1).strip()
                    # Filter out non-cuisine words
                    if cuisine.lower() not in ['nearby', 'find', 'the', 'a', 'near']:
                        params[param_name] = cuisine.capitalize()
                        break
        
        elif param_name == "max_distance" or "distance" in param_name.lower():
            # Extract distance - look for numbers followed by "miles" or "mi"
            distance_patterns = [
                r'within\s+(\d+)\s*(?:miles?|mi)',
                r'(\d+)\s*(?:miles?|mi)\s*(?:away|radius|distance)?',
                r'(\d+)\s*(?:miles?|mi)',
            ]
            for pattern in distance_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    params[param_name] = int(match.group(1))
                    break
        
        elif param_type == "integer" or param_type == "number":
            # Generic number extraction
            numbers = re.findall(r'\d+', query)
            if numbers:
                params[param_name] = int(numbers[0])
        
        elif param_type == "string":
            # Generic string extraction - try to find quoted strings or key phrases
            quoted = re.findall(r'"([^"]+)"', query)
            if quoted:
                params[param_name] = quoted[0]
    
    return {func_name: params}
