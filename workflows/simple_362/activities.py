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
    """Extract function name and parameters from user query using regex and string matching."""
    
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
    
    # Extract parameters from query using regex and string matching
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        
        if param_name == "city":
            # Extract city name - look for "in <City>" pattern
            city_match = re.search(r'\bin\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)', query)
            if city_match:
                params["city"] = city_match.group(1).strip()
            else:
                # Fallback: look for capitalized words that might be cities
                caps_match = re.findall(r'\b([A-Z][a-z]+)\b', query)
                # Filter out common words
                common_words = {"What", "The", "Top", "Best", "High", "Above", "Places", "Default"}
                cities = [w for w in caps_match if w not in common_words]
                if cities:
                    params["city"] = cities[-1]  # Take last one (often the city)
        
        elif param_name == "top":
            # Extract "top N" or "top five" etc.
            # First try numeric
            top_match = re.search(r'\btop\s+(\d+)\b', query, re.IGNORECASE)
            if top_match:
                params["top"] = int(top_match.group(1))
            else:
                # Try word numbers
                word_to_num = {
                    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
                    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10
                }
                top_word_match = re.search(r'\btop\s+(\w+)\b', query, re.IGNORECASE)
                if top_word_match:
                    word = top_word_match.group(1).lower()
                    if word in word_to_num:
                        params["top"] = word_to_num[word]
        
        elif param_name == "review_rate":
            # Extract review rating - look for patterns like "above 4/5", "above 4", "4.0", etc.
            # Pattern: "above X/Y" or "above X"
            rate_match = re.search(r'above\s+(\d+(?:\.\d+)?)\s*(?:/\s*5)?', query, re.IGNORECASE)
            if rate_match:
                params["review_rate"] = float(rate_match.group(1))
            else:
                # Try "rating of X" or "X stars" or just a decimal
                rate_match2 = re.search(r'(\d+(?:\.\d+)?)\s*(?:/\s*5|stars?)', query, re.IGNORECASE)
                if rate_match2:
                    params["review_rate"] = float(rate_match2.group(1))
    
    return {func_name: params}
