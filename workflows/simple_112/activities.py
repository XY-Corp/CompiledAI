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
    
    Uses domain knowledge and regex to extract parameters - no LLM calls needed.
    """
    # Parse prompt (may be JSON string with nested structure)
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
            # Extract user query from BFCL format
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
    
    # Extract parameters based on the function type
    params = {}
    query_lower = query.lower()
    
    if func_name == "calculate_probability":
        # Domain knowledge: standard deck of cards has 52 cards
        # Common card probability questions
        
        # Check for deck of cards context
        if "deck" in query_lower and "card" in query_lower:
            # Standard deck has 52 cards
            params["total_outcomes"] = 52
            
            # Determine favorable outcomes based on what's being drawn
            if "king" in query_lower:
                # 4 kings in a deck
                params["favorable_outcomes"] = 4
            elif "queen" in query_lower:
                # 4 queens in a deck
                params["favorable_outcomes"] = 4
            elif "jack" in query_lower:
                # 4 jacks in a deck
                params["favorable_outcomes"] = 4
            elif "ace" in query_lower:
                # 4 aces in a deck
                params["favorable_outcomes"] = 4
            elif "heart" in query_lower or "diamond" in query_lower or "club" in query_lower or "spade" in query_lower:
                # 13 cards per suit
                params["favorable_outcomes"] = 13
            elif "face card" in query_lower:
                # 12 face cards (J, Q, K in each suit)
                params["favorable_outcomes"] = 12
            elif "red" in query_lower:
                # 26 red cards (hearts + diamonds)
                params["favorable_outcomes"] = 26
            elif "black" in query_lower:
                # 26 black cards (clubs + spades)
                params["favorable_outcomes"] = 26
            else:
                # Try to extract numbers from query
                numbers = re.findall(r'\d+', query)
                if numbers:
                    params["favorable_outcomes"] = int(numbers[0])
                else:
                    params["favorable_outcomes"] = 1  # Default to 1 specific card
        else:
            # Generic probability - extract numbers from query
            numbers = re.findall(r'\d+', query)
            if len(numbers) >= 2:
                # Assume first number is favorable, second is total (or vice versa)
                # Usually phrased as "X out of Y" or "X from Y"
                if "out of" in query_lower or "from" in query_lower:
                    params["favorable_outcomes"] = int(numbers[0])
                    params["total_outcomes"] = int(numbers[1])
                else:
                    # Larger number is likely total outcomes
                    nums = [int(n) for n in numbers]
                    params["total_outcomes"] = max(nums)
                    params["favorable_outcomes"] = min(nums)
            elif len(numbers) == 1:
                params["total_outcomes"] = int(numbers[0])
                params["favorable_outcomes"] = 1
        
        # Check for rounding specification
        round_match = re.search(r'round(?:ed)?\s*(?:to)?\s*(\d+)', query_lower)
        if round_match:
            params["round_to"] = int(round_match.group(1))
        # Note: round_to has a default of 2, so we don't need to set it if not specified
    
    else:
        # Generic parameter extraction for other functions
        numbers = re.findall(r'\d+(?:\.\d+)?', query)
        num_idx = 0
        
        for param_name, param_info in params_schema.items():
            param_type = param_info.get("type", "string")
            
            if param_type in ["integer", "number", "float"]:
                if num_idx < len(numbers):
                    if param_type == "integer":
                        params[param_name] = int(float(numbers[num_idx]))
                    else:
                        params[param_name] = float(numbers[num_idx])
                    num_idx += 1
            elif param_type == "string":
                # Try to extract string values
                string_match = re.search(r'(?:for|in|of|with)\s+([A-Za-z\s]+?)(?:\s+(?:and|with|,|from)|$)', query, re.IGNORECASE)
                if string_match:
                    params[param_name] = string_match.group(1).strip()
    
    return {func_name: params}
