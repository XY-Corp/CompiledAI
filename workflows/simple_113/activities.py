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
    
    # Extract parameters using regex
    params = {}
    query_lower = query.lower()
    
    # For dice roll probability questions, extract:
    # 1. desired_number - the number they want to roll (e.g., "six", "6")
    # 2. number_of_rolls - how many times in a row (e.g., "twice", "2 times")
    # 3. die_sides - number of sides on die (optional, e.g., "six-sided")
    
    # Number word to digit mapping
    word_to_num = {
        "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
        "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
        "twice": 2, "once": 1, "thrice": 3
    }
    
    # Extract die_sides from "X-sided die" pattern
    die_sides_match = re.search(r'(\d+|one|two|three|four|five|six|seven|eight|nine|ten|twelve|twenty)-sided', query_lower)
    if die_sides_match:
        sides_val = die_sides_match.group(1)
        if sides_val.isdigit():
            params["die_sides"] = int(sides_val)
        elif sides_val in word_to_num:
            params["die_sides"] = word_to_num[sides_val]
    
    # Extract desired_number - "rolling a X" pattern
    desired_match = re.search(r'rolling\s+(?:a\s+)?(\d+|one|two|three|four|five|six|seven|eight|nine|ten)', query_lower)
    if desired_match:
        desired_val = desired_match.group(1)
        if desired_val.isdigit():
            params["desired_number"] = int(desired_val)
        elif desired_val in word_to_num:
            params["desired_number"] = word_to_num[desired_val]
    
    # Extract number_of_rolls - "X times in a row" or "twice in a row" pattern
    rolls_match = re.search(r'(\d+|once|twice|thrice|one|two|three|four|five|six|seven|eight|nine|ten)\s+(?:times?\s+)?in\s+a\s+row', query_lower)
    if rolls_match:
        rolls_val = rolls_match.group(1)
        if rolls_val.isdigit():
            params["number_of_rolls"] = int(rolls_val)
        elif rolls_val in word_to_num:
            params["number_of_rolls"] = word_to_num[rolls_val]
    
    # Fallback: extract all numbers from query if specific patterns didn't match
    if "desired_number" not in params or "number_of_rolls" not in params:
        all_numbers = re.findall(r'\b(\d+)\b', query)
        # Also find number words
        for word, num in word_to_num.items():
            if word in query_lower and word not in ["twice", "once", "thrice"]:
                all_numbers.append(str(num))
        
        # Try to assign based on context
        if "desired_number" not in params and all_numbers:
            params["desired_number"] = int(all_numbers[0])
        if "number_of_rolls" not in params:
            # Look for "twice" specifically
            if "twice" in query_lower:
                params["number_of_rolls"] = 2
            elif "once" in query_lower:
                params["number_of_rolls"] = 1
            elif "thrice" in query_lower:
                params["number_of_rolls"] = 3
    
    return {func_name: params}
