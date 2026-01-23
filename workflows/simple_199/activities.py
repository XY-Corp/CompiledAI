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
    
    # Extract parameters based on schema
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        
        if param_type == "integer" or param_type == "number":
            # Extract numbers from query
            # Look for patterns like "next three days", "3 days", "for 5 days"
            number_words = {
                "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
                "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10
            }
            
            # Try word numbers first (e.g., "next three days")
            word_pattern = r'(?:next|for|over)\s+(\w+)\s+days?'
            word_match = re.search(word_pattern, query, re.IGNORECASE)
            if word_match:
                word = word_match.group(1).lower()
                if word in number_words:
                    params[param_name] = number_words[word]
                    continue
            
            # Try numeric patterns (e.g., "3 days", "for 5 days")
            num_pattern = r'(\d+)\s*days?'
            num_match = re.search(num_pattern, query, re.IGNORECASE)
            if num_match:
                params[param_name] = int(num_match.group(1))
                continue
            
            # Generic number extraction as fallback
            numbers = re.findall(r'\d+', query)
            if numbers:
                params[param_name] = int(numbers[0])
        
        elif param_type == "string":
            # Extract location/city names
            if "location" in param_name.lower() or "city" in param_name.lower():
                # Patterns for location extraction
                location_patterns = [
                    r'(?:in|for|at)\s+([A-Z][a-zA-Z\s]+?)(?:\s+for|\s+over|\s+next|\s*$|\s*\.)',
                    r'(?:in|for|at)\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)?)',
                ]
                
                for pattern in location_patterns:
                    match = re.search(pattern, query)
                    if match:
                        location = match.group(1).strip()
                        # Clean up trailing words that aren't part of location
                        location = re.sub(r'\s+(?:for|over|next|today|tomorrow).*$', '', location, flags=re.IGNORECASE)
                        if location:
                            params[param_name] = location
                            break
    
    return {func_name: params}
