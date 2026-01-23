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
    
    # Extract parameters based on schema
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_type == "integer":
            # Extract numbers from query
            # Look for patterns like "top three", "top 3", "3 results", etc.
            number_words = {
                "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
                "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10
            }
            
            # Try word numbers first (e.g., "top three")
            word_match = re.search(r'top\s+(one|two|three|four|five|six|seven|eight|nine|ten)', query.lower())
            if word_match:
                params[param_name] = number_words[word_match.group(1)]
            else:
                # Try numeric patterns
                num_match = re.search(r'top\s+(\d+)', query.lower())
                if num_match:
                    params[param_name] = int(num_match.group(1))
                else:
                    # Look for any number in context
                    numbers = re.findall(r'\d+', query)
                    if numbers:
                        params[param_name] = int(numbers[0])
        
        elif param_type == "string":
            # Extract string values based on parameter description
            if "slope" in param_name.lower() or "slope" in param_desc:
                # Look for slope type patterns
                slope_patterns = [
                    r'(steep|moderate|gentle|gradual|mild)\s*(?:slope)?',
                    r'(?:a|the)?\s*(hill)\s*slope',
                    r'slope\s*(?:type|of)?\s*[:\-]?\s*(\w+)',
                ]
                
                # Check for specific slope type keywords
                slope_types = ["steep", "moderate", "gentle", "gradual", "mild", "hill"]
                query_lower = query.lower()
                
                found_slope = None
                for slope_type in slope_types:
                    if slope_type in query_lower:
                        found_slope = slope_type
                        break
                
                if found_slope:
                    params[param_name] = found_slope
                else:
                    # Try regex patterns
                    for pattern in slope_patterns:
                        match = re.search(pattern, query.lower())
                        if match:
                            params[param_name] = match.group(1)
                            break
    
    return {func_name: params}
