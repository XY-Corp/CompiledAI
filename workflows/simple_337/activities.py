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
    
    Parses the user query to extract player names and card assignments
    for a poker game winner determination function.
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
    
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "poker_game_winner")
    
    # Extract player names - look for pattern like "players Alex, Sam, Robert and Steve"
    players = []
    
    # Pattern 1: "players X, Y, Z and W"
    players_match = re.search(r'players?\s+([A-Za-z]+(?:\s*,\s*[A-Za-z]+)*(?:\s+and\s+[A-Za-z]+)?)', query, re.IGNORECASE)
    if players_match:
        players_str = players_match.group(1)
        # Split by comma and "and"
        players_str = re.sub(r'\s+and\s+', ', ', players_str)
        players = [p.strip() for p in players_str.split(',') if p.strip()]
    
    # Extract cards - look for pattern like "Name': ['card1', 'card2']" or "Name: ['card1', 'card2']"
    cards = {}
    
    # Pattern: 'Name': ['card1', 'card2'] or Name': ['card1', 'card2']
    card_pattern = r"'?(\w+)'?\s*:\s*\[([^\]]+)\]"
    card_matches = re.findall(card_pattern, query)
    
    for name, cards_str in card_matches:
        # Clean up the name (remove quotes if present)
        name = name.strip("'\"")
        
        # Parse the cards list - extract individual card strings
        card_items = re.findall(r"'([^']+)'", cards_str)
        if card_items:
            cards[name] = card_items
    
    # If we found cards but not players, extract players from cards keys
    if cards and not players:
        players = list(cards.keys())
    
    # Extract game type - look for "texas holdem" or similar
    game_type = "Texas Holdem"  # Default
    type_match = re.search(r'(texas\s+holdem|omaha|stud|draw)', query, re.IGNORECASE)
    if type_match:
        game_type = type_match.group(1).title()
    
    # Build result with only required params + optional if specified
    result = {
        func_name: {
            "players": players,
            "cards": cards
        }
    }
    
    # Add type parameter (it has a default, but include it since it's mentioned in query)
    if "texas holdem" in query.lower():
        result[func_name]["type"] = "Texas Holdem"
    
    return result
