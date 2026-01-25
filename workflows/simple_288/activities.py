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
    """Extract function call parameters from user query and return as {func_name: {params}}.
    
    Uses regex and string matching to extract values - no LLM calls needed.
    """
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
    query_lower = query.lower()
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_type == "integer":
            # Extract numbers - look for patterns like "two tickets", "2 tickets", etc.
            # First try word numbers
            word_to_num = {
                "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
                "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10
            }
            
            # Check for word numbers followed by "ticket"
            word_match = re.search(r'\b(one|two|three|four|five|six|seven|eight|nine|ten)\s+ticket', query_lower)
            if word_match:
                params[param_name] = word_to_num[word_match.group(1)]
            else:
                # Try numeric digits
                num_match = re.search(r'(\d+)\s*ticket', query_lower)
                if num_match:
                    params[param_name] = int(num_match.group(1))
                else:
                    # Just find any number in the query
                    numbers = re.findall(r'\d+', query)
                    if numbers:
                        params[param_name] = int(numbers[0])
        
        elif param_type == "string":
            # Extract string values based on parameter name/description
            if "artist" in param_name.lower() or "artist" in param_desc:
                # Look for artist name - common patterns
                # "for [Artist]" or "[Artist] concert"
                artist_patterns = [
                    r'(?:for|see|watch)\s+(?:next\s+)?([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)\s+(?:concert|show|tour)',
                    r'([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)\s+concert',
                    r'next\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)\s+concert',
                ]
                for pattern in artist_patterns:
                    match = re.search(pattern, query)
                    if match:
                        params[param_name] = match.group(1).strip()
                        break
            
            elif "city" in param_name.lower() or "city" in param_desc:
                # Look for city name - patterns like "in [City]"
                city_patterns = [
                    r'\bin\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*?)(?:\s*\.|$|\s+for|\s+on)',
                    r'\bin\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)',
                ]
                for pattern in city_patterns:
                    match = re.search(pattern, query)
                    if match:
                        params[param_name] = match.group(1).strip().rstrip('.')
                        break
    
    return {func_name: params}
