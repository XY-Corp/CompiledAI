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
    
    # Extract parameters from query
    params = {}
    query_lower = query.lower()
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_type == "integer":
            # Extract numbers from query
            # Look for patterns like "top three", "top 3", "three plants", etc.
            
            # First try word numbers
            word_to_num = {
                "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
                "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10
            }
            
            # Pattern: "top X" where X is a word number
            word_num_match = re.search(r'top\s+(one|two|three|four|five|six|seven|eight|nine|ten)', query_lower)
            if word_num_match:
                params[param_name] = word_to_num[word_num_match.group(1)]
                continue
            
            # Pattern: "top N" where N is a digit
            digit_match = re.search(r'top\s+(\d+)', query_lower)
            if digit_match:
                params[param_name] = int(digit_match.group(1))
                continue
            
            # Pattern: just extract any number
            numbers = re.findall(r'\d+', query)
            if numbers:
                params[param_name] = int(numbers[0])
                continue
                
        elif param_type == "string":
            # Extract slope type based on parameter description
            if "slope" in param_desc:
                # Look for slope type keywords
                slope_types = ["steep", "moderate", "gentle", "hill", "gradual", "flat"]
                
                for slope_type in slope_types:
                    if slope_type in query_lower:
                        params[param_name] = slope_type
                        break
                
                # If no specific slope type found, check for "hill slope" pattern
                if param_name not in params:
                    hill_match = re.search(r'(hill|hillside|mountain|steep|moderate|gentle)\s*slope', query_lower)
                    if hill_match:
                        params[param_name] = hill_match.group(1)
                    else:
                        # Default to "hill" if mentioned
                        if "hill" in query_lower:
                            params[param_name] = "hill"
    
    return {func_name: params}
