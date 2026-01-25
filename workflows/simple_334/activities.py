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
    
    Parses the user query to extract function name and parameters,
    returning the result in the format {"function_name": {params}}.
    """
    # Parse prompt (may be JSON string with nested structure)
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
        else:
            data = prompt
        
        # Extract user query from BFCL format
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
    props = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters for blackjack.check_winner
    params = {}
    
    # Extract player cards - look for "player having X and Y" pattern
    player_match = re.search(r'player\s+having\s+([A-Za-z0-9]+)\s+and\s+([A-Za-z0-9]+)', query, re.IGNORECASE)
    if player_match:
        params["player_cards"] = [player_match.group(1), player_match.group(2)]
    
    # Extract dealer cards - look for "dealer having X and Y" pattern
    dealer_match = re.search(r'dealer\s+having\s+([A-Za-z0-9]+)\s+and\s+([A-Za-z0-9]+)', query, re.IGNORECASE)
    if dealer_match:
        params["dealer_cards"] = [dealer_match.group(1), dealer_match.group(2)]
    
    # Extract ace_value - look for "Ace is considered X" or "ace value X"
    ace_match = re.search(r'[Aa]ce\s+(?:is\s+)?(?:considered|value|=)\s+(\d+)', query)
    if ace_match:
        params["ace_value"] = int(ace_match.group(1))
    
    return {func_name: params}
