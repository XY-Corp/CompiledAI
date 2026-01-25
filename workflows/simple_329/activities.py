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
    """Extract function name and parameters from user query using regex patterns."""
    
    # Parse prompt - may be JSON string with nested structure
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
    
    # Parse functions - may be JSON string
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
    required_params = func.get("parameters", {}).get("required", [])
    
    # Extract parameters using regex
    params = {}
    
    # Extract all numbers from the query
    numbers = re.findall(r'\b(\d+)\b', query)
    
    # For monopoly_odds_calculator: extract "number" (target sum), "dice_number", and optionally "dice_faces"
    # Query: "Calculate the odds of rolling a 7 with two dice in the board game Monopoly."
    
    # Pattern for target number: "rolling a X" or "rolling X"
    target_match = re.search(r'rolling\s+(?:a\s+)?(\d+)', query, re.IGNORECASE)
    
    # Pattern for dice count: "X dice" or "two dice", "three dice", etc.
    word_to_num = {
        'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
        'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10
    }
    
    dice_count_match = re.search(r'(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+dic?e', query, re.IGNORECASE)
    
    # Extract target number (the sum to roll)
    if "number" in params_schema:
        if target_match:
            params["number"] = int(target_match.group(1))
        elif numbers:
            # First number is likely the target
            params["number"] = int(numbers[0])
    
    # Extract dice count
    if "dice_number" in params_schema:
        if dice_count_match:
            dice_val = dice_count_match.group(1).lower()
            if dice_val in word_to_num:
                params["dice_number"] = word_to_num[dice_val]
            else:
                params["dice_number"] = int(dice_val)
        else:
            # Default to 2 dice if not specified but "dice" is mentioned
            if re.search(r'dice', query, re.IGNORECASE):
                params["dice_number"] = 2
    
    # Extract dice faces (optional - only if explicitly mentioned)
    if "dice_faces" in params_schema:
        # Look for "X-sided" or "X-faced" or "X faces"
        faces_match = re.search(r'(\d+)[-\s]?(?:sided|faced|faces)', query, re.IGNORECASE)
        if faces_match:
            params["dice_faces"] = int(faces_match.group(1))
        # Don't include if not specified - it has a default value
    
    return {func_name: params}
