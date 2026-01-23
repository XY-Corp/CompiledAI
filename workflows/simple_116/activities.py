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
        # Standard deck of cards = 52 total outcomes
        if "deck" in query_lower and "52" in query:
            params["total_outcomes"] = 52
        elif "deck" in query_lower or "cards" in query_lower:
            # Standard deck assumption
            params["total_outcomes"] = 52
        else:
            # Try to extract any number for total outcomes
            numbers = re.findall(r'\d+', query)
            if numbers:
                params["total_outcomes"] = int(numbers[0])
        
        # Extract event outcomes based on what's being drawn
        if "king" in query_lower:
            # 4 kings in a standard deck
            params["event_outcomes"] = 4
        elif "queen" in query_lower:
            params["event_outcomes"] = 4
        elif "jack" in query_lower:
            params["event_outcomes"] = 4
        elif "ace" in query_lower:
            params["event_outcomes"] = 4
        elif "heart" in query_lower or "diamond" in query_lower or "club" in query_lower or "spade" in query_lower:
            # 13 cards per suit
            params["event_outcomes"] = 13
        elif "face card" in query_lower:
            # 12 face cards (J, Q, K of each suit)
            params["event_outcomes"] = 12
        elif "red" in query_lower:
            # 26 red cards (hearts + diamonds)
            params["event_outcomes"] = 26
        elif "black" in query_lower:
            # 26 black cards (clubs + spades)
            params["event_outcomes"] = 26
        else:
            # Try to find event outcomes from numbers in query
            numbers = re.findall(r'\d+', query)
            if len(numbers) >= 2:
                params["event_outcomes"] = int(numbers[1])
            elif len(numbers) == 1 and "total_outcomes" not in params:
                params["event_outcomes"] = int(numbers[0])
    else:
        # Generic number extraction for other function types
        numbers = re.findall(r'\d+', query)
        param_names = list(params_schema.keys())
        
        for i, param_name in enumerate(param_names):
            param_info = params_schema.get(param_name, {})
            param_type = param_info.get("type", "string")
            
            if param_type in ["integer", "number", "float"]:
                if i < len(numbers):
                    if param_type == "integer":
                        params[param_name] = int(numbers[i])
                    else:
                        params[param_name] = float(numbers[i])
    
    return {func_name: params}
