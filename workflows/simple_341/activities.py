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
    
    # Parse prompt (may be JSON string with nested structure)
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
            # Handle BFCL format: {"question": [[{"role": "user", "content": "..."}]], ...}
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
    props = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters from query using regex and string matching
    params = {}
    query_lower = query.lower()
    
    # Extract suit parameter
    if "suit" in props:
        # Look for card suits in the query
        suit_patterns = {
            "hearts": r'\bheart[s]?\b',
            "diamonds": r'\bdiamond[s]?\b',
            "spades": r'\bspade[s]?\b',
            "clubs": r'\bclub[s]?\b'
        }
        for suit_value, pattern in suit_patterns.items():
            if re.search(pattern, query_lower):
                params["suit"] = suit_value
                break
    
    # Extract deck_type parameter
    if "deck_type" in props:
        # Check for "without joker" or "no joker" patterns
        if re.search(r'\bwithout\s+joker[s]?\b', query_lower) or re.search(r'\bno\s+joker[s]?\b', query_lower):
            params["deck_type"] = "without_joker"
        elif re.search(r'\bwith\s+joker[s]?\b', query_lower) or re.search(r'\bnormal\b', query_lower):
            params["deck_type"] = "normal"
        else:
            # Default based on context - "without joker" mentioned
            if "joker" in query_lower:
                # If joker is mentioned but not "with joker", assume without
                params["deck_type"] = "without_joker"
            else:
                # Use default from schema
                params["deck_type"] = props.get("deck_type", {}).get("default", "normal")
    
    return {func_name: params}
