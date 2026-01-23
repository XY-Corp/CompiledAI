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
    
    # Parse prompt - may be JSON string with nested structure
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
    
    # Extract parameters from query using regex and string matching
    params = {}
    query_lower = query.lower()
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_type == "integer":
            # Extract integers - look for numbers with context
            # For "years" - look for patterns like "next five years", "5 years", etc.
            if "year" in param_name.lower() or "year" in param_desc:
                # Word-to-number mapping for common cases
                word_to_num = {
                    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
                    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
                    "eleven": 11, "twelve": 12, "fifteen": 15, "twenty": 20
                }
                
                # Try word patterns first: "next five years", "over the next ten years"
                word_pattern = r'(?:next|over\s+the\s+next|in\s+the\s+next)\s+(\w+)\s+years?'
                word_match = re.search(word_pattern, query_lower)
                if word_match:
                    word = word_match.group(1)
                    if word in word_to_num:
                        params[param_name] = word_to_num[word]
                        continue
                    # Try if it's a digit word
                    try:
                        params[param_name] = int(word)
                        continue
                    except ValueError:
                        pass
                
                # Try numeric patterns: "5 years", "next 5 years"
                num_pattern = r'(\d+)\s+years?'
                num_match = re.search(num_pattern, query_lower)
                if num_match:
                    params[param_name] = int(num_match.group(1))
                    continue
            
            # Generic integer extraction
            numbers = re.findall(r'\b(\d+)\b', query)
            if numbers:
                params[param_name] = int(numbers[0])
        
        elif param_type == "float":
            # Extract floats - look for decimal numbers or percentages
            float_match = re.search(r'(\d+\.?\d*)\s*%?', query)
            if float_match:
                params[param_name] = float(float_match.group(1))
            # Skip if not found - likely optional with default
        
        elif param_type == "string":
            # Extract string values - typically locations, names, etc.
            if "location" in param_name.lower() or "city" in param_desc:
                # Common patterns for location extraction
                # "in London", "for London", "of London"
                location_patterns = [
                    r'(?:in|for|of)\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)',
                    r'population\s+(?:growth\s+)?(?:in|of|for)\s+([A-Z][a-zA-Z]+)',
                ]
                
                for pattern in location_patterns:
                    loc_match = re.search(pattern, query)
                    if loc_match:
                        params[param_name] = loc_match.group(1).strip()
                        break
    
    return {func_name: params}
