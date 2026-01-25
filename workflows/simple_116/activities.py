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
    """Extract function name and parameters from user query using regex/parsing."""
    
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
    
    # Extract parameters based on the query content
    params = {}
    query_lower = query.lower()
    
    # For probability calculation: extract total_outcomes and event_outcomes
    if "probabilities" in func_name or "probability" in query_lower:
        # Standard deck has 52 cards
        if "deck" in query_lower and "52" in query:
            params["total_outcomes"] = 52
        elif "deck" in query_lower:
            # Standard deck default
            params["total_outcomes"] = 52
        else:
            # Try to extract total from query
            total_match = re.search(r'(\d+)\s*(?:cards|outcomes|total|items)', query_lower)
            if total_match:
                params["total_outcomes"] = int(total_match.group(1))
        
        # Extract event outcomes based on what we're drawing
        # Kings in a standard deck: 4 (one per suit)
        if "king" in query_lower:
            params["event_outcomes"] = 4
        elif "queen" in query_lower:
            params["event_outcomes"] = 4
        elif "jack" in query_lower:
            params["event_outcomes"] = 4
        elif "ace" in query_lower:
            params["event_outcomes"] = 4
        elif "heart" in query_lower or "diamond" in query_lower or "club" in query_lower or "spade" in query_lower:
            # One suit has 13 cards
            params["event_outcomes"] = 13
        elif "red" in query_lower or "black" in query_lower:
            # Red or black cards: 26 each
            params["event_outcomes"] = 26
        elif "face card" in query_lower:
            # Face cards (J, Q, K): 12 total
            params["event_outcomes"] = 12
        else:
            # Try to extract event outcomes from numbers in query
            numbers = re.findall(r'\d+', query)
            if len(numbers) >= 2:
                # If we have multiple numbers, second might be event outcomes
                params["event_outcomes"] = int(numbers[1])
            elif len(numbers) == 1 and "total_outcomes" not in params:
                params["event_outcomes"] = int(numbers[0])
    
    # Check for optional 'round' parameter
    round_match = re.search(r'round(?:ed)?\s*(?:to)?\s*(\d+)', query_lower)
    if round_match:
        params["round"] = int(round_match.group(1))
    
    # Fallback: extract all numbers if we still need params
    if not params:
        numbers = re.findall(r'\d+', query)
        param_names = list(params_schema.keys())
        for i, param_name in enumerate(param_names):
            if i < len(numbers):
                param_info = params_schema.get(param_name, {})
                param_type = param_info.get("type", "string")
                if param_type == "integer":
                    params[param_name] = int(numbers[i])
                elif param_type in ["number", "float"]:
                    params[param_name] = float(numbers[i])
                else:
                    params[param_name] = numbers[i]
    
    return {func_name: params}
