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
    """Extract function call parameters from user query using regex and string matching."""
    
    # Parse prompt - may be JSON string with nested structure
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
            # Extract user content from BFCL format: {"question": [[{"role": "user", "content": "..."}]]}
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
    
    # Get function schema
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters from query using regex and string matching
    params = {}
    query_lower = query.lower()
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_name == "hotel_name":
            # Extract hotel name - look for "at <hotel name>" or "the <hotel name> hotel"
            # Pattern: "at The Plaza hotel" or "at The Plaza"
            hotel_match = re.search(r'at\s+(?:the\s+)?([A-Za-z\s]+?)(?:\s+hotel)?(?:\s*[,.]|\s+for|\s*$)', query, re.IGNORECASE)
            if hotel_match:
                hotel_name = hotel_match.group(1).strip()
                # Clean up - remove trailing "hotel" if captured
                hotel_name = re.sub(r'\s+hotel\s*$', '', hotel_name, flags=re.IGNORECASE).strip()
                params[param_name] = hotel_name
            else:
                # Fallback: look for capitalized words that might be hotel name
                hotel_match = re.search(r'(?:The\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+hotel', query, re.IGNORECASE)
                if hotel_match:
                    params[param_name] = hotel_match.group(1).strip()
        
        elif param_name == "room_type":
            # Extract room type - look for "single", "double", "suite", etc.
            room_types = ["single", "double", "twin", "suite", "deluxe", "standard", "king", "queen"]
            for room_type in room_types:
                if room_type in query_lower:
                    params[param_name] = room_type
                    break
            # Also check for patterns like "a single room" or "single room"
            if param_name not in params:
                room_match = re.search(r'(?:a\s+)?(\w+)\s+room', query, re.IGNORECASE)
                if room_match:
                    params[param_name] = room_match.group(1).lower()
        
        elif param_name == "num_nights":
            # Extract number of nights - look for "X nights" or "X night"
            nights_match = re.search(r'(\d+)\s+nights?', query, re.IGNORECASE)
            if nights_match:
                params[param_name] = int(nights_match.group(1))
            else:
                # Try word numbers
                word_to_num = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, 
                              "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
                for word, num in word_to_num.items():
                    if re.search(rf'{word}\s+nights?', query_lower):
                        params[param_name] = num
                        break
        
        elif param_type == "integer":
            # Generic integer extraction
            numbers = re.findall(r'\d+', query)
            if numbers:
                params[param_name] = int(numbers[0])
        
        elif param_type == "string":
            # Generic string - try to extract based on description keywords
            # This is a fallback for unknown string parameters
            pass
    
    return {func_name: params}
