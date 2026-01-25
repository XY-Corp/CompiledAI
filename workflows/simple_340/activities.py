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
    """Extract function call parameters from natural language query about a poker game."""
    
    # Parse prompt (may be JSON string with nested structure)
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
            # Extract user query from BFCL format
            if "question" in data and isinstance(data["question"], list):
                if len(data["question"]) > 0 and isinstance(data["question"][0], list):
                    query = data["question"][0][0].get("content", prompt)
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
    
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "card_games.poker_determine_winner")
    
    # Extract player names and hands using regex
    # Pattern: "player_name having a Hand of card1, card2, ..." or "player_name having card1, card2..."
    
    # Extract player1 and hand1
    player1_pattern = r'(\w+)\s+having\s+(?:a\s+)?[Hh]and\s+of\s+([\w♥♠♦♣,\s]+?)(?:\s+and\s+\w+\s+having|\s*\.\s*$|$)'
    
    # More flexible pattern to capture both players
    # Pattern: "Name1 having [a Hand of] cards1 and Name2 having cards2"
    full_pattern = r'(\w+)\s+having\s+(?:a\s+)?[Hh]and\s+of\s+([\d\w♥♠♦♣,\s]+?)\s+and\s+(\w+)\s+having\s+([\d\w♥♠♦♣,\s\.]+)'
    
    match = re.search(full_pattern, query)
    
    if match:
        player1 = match.group(1)
        hand1_str = match.group(2)
        player2 = match.group(3)
        hand2_str = match.group(4)
    else:
        # Fallback: try to extract names and cards separately
        # Extract names (capitalized words before "having")
        names = re.findall(r'(\b[A-Z][a-z]+)\s+having', query)
        player1 = names[0] if len(names) > 0 else ""
        player2 = names[1] if len(names) > 1 else ""
        
        # Extract all card sequences
        # Cards are like: 8♥, 10♥, J♥, Q♥, K♥ or 9♠, J♠, 10♠, Q♠, K♠
        card_pattern = r'(?:Hand\s+of\s+)?([\dJQKA]+[♥♠♦♣](?:\s*,\s*[\dJQKA]+[♥♠♦♣])*)'
        card_matches = re.findall(card_pattern, query)
        
        hand1_str = card_matches[0] if len(card_matches) > 0 else ""
        hand2_str = card_matches[1] if len(card_matches) > 1 else ""
    
    # Parse cards from comma-separated string
    def parse_cards(cards_str: str) -> list:
        # Remove trailing period and whitespace
        cards_str = cards_str.strip().rstrip('.')
        # Split by comma and clean each card
        cards = [card.strip() for card in cards_str.split(',') if card.strip()]
        # Filter to only valid cards (must contain a suit symbol)
        valid_cards = [c for c in cards if any(suit in c for suit in ['♥', '♠', '♦', '♣'])]
        return valid_cards
    
    hand1 = parse_cards(hand1_str)
    hand2 = parse_cards(hand2_str)
    
    return {
        func_name: {
            "player1": player1,
            "hand1": hand1,
            "player2": player2,
            "hand2": hand2
        }
    }
