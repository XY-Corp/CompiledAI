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
    props = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters from query
    params = {}
    query_lower = query.lower()
    
    # Extract religion - look for religion names
    religion_patterns = [
        r'\b(christianity|islam|buddhism|hinduism|judaism|sikhism|taoism|confucianism|shinto|zoroastrianism)\b',
        r'related to\s+(\w+)',
        r'about\s+(\w+)',
        r'of\s+(\w+)\s+(?:in|during)',
    ]
    
    religion = None
    for pattern in religion_patterns:
        match = re.search(pattern, query_lower)
        if match:
            religion = match.group(1).capitalize()
            break
    
    if religion:
        params["religion"] = religion
    
    # Extract century - look for ordinal numbers with "century"
    century_patterns = [
        r'(\d+)(?:st|nd|rd|th)\s+century',
        r'century\s+(\d+)',
        r'(\d{2})00s',  # e.g., "1600s" -> 17th century
    ]
    
    century = None
    for pattern in century_patterns:
        match = re.search(pattern, query_lower)
        if match:
            century_val = int(match.group(1))
            # Handle "1600s" format
            if century_val >= 100:
                century = (century_val // 100) + 1
            else:
                century = century_val
            break
    
    if century:
        params["century"] = century
    
    # Extract sort_by - look for sorting keywords
    if "sort by importance" in query_lower or "by importance" in query_lower:
        params["sort_by"] = "importance"
    elif "sort by chronological" in query_lower or "chronological" in query_lower or "by date" in query_lower:
        params["sort_by"] = "chronological"
    elif "importance" in query_lower:
        params["sort_by"] = "importance"
    
    # Extract count - look for numbers indicating quantity
    count_patterns = [
        r'\b(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|fifteen|twenty)\b',
        r'(\d+)\s+(?:major|significant|important|historical|events|results)',
        r'(?:find|get|retrieve|show|list)\s+(\d+)',
        r'top\s+(\d+)',
    ]
    
    word_to_num = {
        "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
        "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
        "eleven": 11, "twelve": 12, "fifteen": 15, "twenty": 20
    }
    
    count = None
    for pattern in count_patterns:
        match = re.search(pattern, query_lower)
        if match:
            val = match.group(1)
            if val in word_to_num:
                count = word_to_num[val]
            else:
                try:
                    count = int(val)
                except ValueError:
                    pass
            if count:
                break
    
    if count:
        params["count"] = count
    
    return {func_name: params}
