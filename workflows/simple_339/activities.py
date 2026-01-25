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
    
    Uses regex and string parsing to extract values - no LLM calls needed.
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
    
    # Extract all numbers from query
    numbers = re.findall(r'\d+', query)
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_type == "integer":
            # Try to find specific number based on context
            if "deck" in param_name.lower() or "deck" in param_desc:
                # Look for deck size - default is 52
                deck_match = re.search(r'(\d+)\s*(?:card|deck)', query, re.IGNORECASE)
                if deck_match:
                    params[param_name] = int(deck_match.group(1))
                else:
                    # Use default from description if mentioned
                    default_match = re.search(r'default\s*(?:is|=|:)?\s*(\d+)', param_desc)
                    if default_match:
                        params[param_name] = int(default_match.group(1))
                    elif numbers:
                        params[param_name] = int(numbers[0])
                    else:
                        params[param_name] = 52  # Standard deck size
                        
            elif "hand" in param_name.lower() or "hand" in param_desc:
                # Look for hand size - default is 5
                hand_match = re.search(r'(\d+)\s*(?:card|hand)', query, re.IGNORECASE)
                if hand_match:
                    params[param_name] = int(hand_match.group(1))
                else:
                    # Use default from description if mentioned
                    default_match = re.search(r'default\s*(?:is|=|:)?\s*(\d+)', param_desc)
                    if default_match:
                        params[param_name] = int(default_match.group(1))
                    elif len(numbers) > 1:
                        params[param_name] = int(numbers[1])
                    else:
                        params[param_name] = 5  # Standard poker hand size
            else:
                # Generic integer extraction
                default_match = re.search(r'default\s*(?:is|=|:)?\s*(\d+)', param_desc)
                if default_match:
                    params[param_name] = int(default_match.group(1))
                elif numbers:
                    params[param_name] = int(numbers.pop(0))
                    
        elif param_type == "string":
            # Extract string values using common patterns
            string_match = re.search(r'(?:for|in|of|with|called|named)\s+["\']?([A-Za-z\s]+)["\']?', query, re.IGNORECASE)
            if string_match:
                params[param_name] = string_match.group(1).strip()
    
    return {func_name: params}
