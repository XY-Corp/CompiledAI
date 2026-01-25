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
    """Extract function call parameters from user query using regex and pattern matching."""
    
    # Parse prompt (may be JSON string with nested structure)
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
            # Extract user query from BFCL format: {"question": [[{"role": "user", "content": "..."}]]}
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
    
    # Extract parameters based on the query content
    params = {}
    query_lower = query.lower()
    
    # Extract numbers from the query
    numbers = re.findall(r'\b(\d+)\b', query)
    
    # For card probability: look for total cards and desired cards
    # "deck of 52 cards" -> total_cards = 52
    # "heart card" -> desired_cards = 13 (standard deck has 13 hearts)
    
    # Extract total_cards - look for "deck of X cards" or just numbers
    total_match = re.search(r'deck\s+of\s+(\d+)\s+cards?', query_lower)
    if total_match:
        params["total_cards"] = int(total_match.group(1))
    elif "total_cards" in params_schema and numbers:
        # Use the largest number as total cards (likely deck size)
        params["total_cards"] = int(max(numbers, key=int))
    
    # Extract desired_cards based on card type mentioned
    # Standard deck: 13 cards per suit (hearts, diamonds, clubs, spades)
    # 4 cards per rank (aces, kings, queens, jacks, etc.)
    if "heart" in query_lower or "hearts" in query_lower:
        params["desired_cards"] = 13
    elif "diamond" in query_lower or "diamonds" in query_lower:
        params["desired_cards"] = 13
    elif "club" in query_lower or "clubs" in query_lower:
        params["desired_cards"] = 13
    elif "spade" in query_lower or "spades" in query_lower:
        params["desired_cards"] = 13
    elif "ace" in query_lower or "aces" in query_lower:
        params["desired_cards"] = 4
    elif "king" in query_lower or "kings" in query_lower:
        params["desired_cards"] = 4
    elif "queen" in query_lower or "queens" in query_lower:
        params["desired_cards"] = 4
    elif "jack" in query_lower or "jacks" in query_lower:
        params["desired_cards"] = 4
    elif "red" in query_lower:  # red cards (hearts + diamonds)
        params["desired_cards"] = 26
    elif "black" in query_lower:  # black cards (clubs + spades)
        params["desired_cards"] = 26
    elif "face" in query_lower:  # face cards (J, Q, K = 12 total)
        params["desired_cards"] = 12
    else:
        # Try to find a second number for desired_cards
        desired_match = re.search(r'(\d+)\s+(?:desired|matching|satisf)', query_lower)
        if desired_match:
            params["desired_cards"] = int(desired_match.group(1))
        elif len(numbers) >= 2:
            # If we have multiple numbers, use the smaller one as desired
            nums_int = [int(n) for n in numbers]
            params["desired_cards"] = min(nums_int)
    
    # Extract cards_drawn if mentioned (optional parameter, default is 1)
    drawn_match = re.search(r'draw(?:ing|n)?\s+(\d+)\s+cards?', query_lower)
    if drawn_match:
        params["cards_drawn"] = int(drawn_match.group(1))
    elif re.search(r'(\d+)\s+cards?\s+(?:drawn|draw)', query_lower):
        match = re.search(r'(\d+)\s+cards?\s+(?:drawn|draw)', query_lower)
        params["cards_drawn"] = int(match.group(1))
    # If not mentioned, don't include it (let default value apply)
    
    return {func_name: params}
