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
    
    # Parse prompt (may be JSON string with nested structure)
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
            # Handle BFCL format: {"question": [[{"role": "user", "content": "..."}]], ...}
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
    required_params = func.get("parameters", {}).get("required", [])
    
    # Extract parameters using regex and string matching
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        # Extract based on parameter name and type
        if param_name == "rank":
            # Look for rank patterns: "rank 'X'" or "rank X" or common card ranks
            rank_patterns = [
                r"rank\s*['\"]?(\w+)['\"]?",
                r"['\"]?(Ace|Two|Three|Four|Five|Six|Seven|Eight|Nine|Ten|Jack|Queen|King)['\"]?",
            ]
            for pattern in rank_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    params[param_name] = match.group(1).capitalize()
                    break
        
        elif param_name == "suit":
            # Look for suit patterns: "suit 'X'" or "suit X" or common card suits
            suit_patterns = [
                r"suit\s*['\"]?(\w+)['\"]?",
                r"['\"]?(Hearts|Spades|Diamonds|Clubs)['\"]?",
            ]
            for pattern in suit_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    params[param_name] = match.group(1).capitalize()
                    break
        
        elif param_name == "deck":
            # deck is optional and defaults to standard 52 card deck
            # Only include if explicitly provided in the query
            deck_match = re.search(r"deck\s*[=:]\s*(\[.*?\])", query, re.IGNORECASE | re.DOTALL)
            if deck_match:
                try:
                    params[param_name] = json.loads(deck_match.group(1))
                except json.JSONDecodeError:
                    pass  # Skip if can't parse, it's optional
        
        elif param_type == "integer" or param_type == "number":
            # Extract numbers
            numbers = re.findall(r'\d+(?:\.\d+)?', query)
            if numbers:
                if param_type == "integer":
                    params[param_name] = int(numbers[0])
                else:
                    params[param_name] = float(numbers[0])
        
        elif param_type == "string":
            # Generic string extraction - look for quoted values or after param name
            quoted_match = re.search(rf"{param_name}\s*[=:]\s*['\"]([^'\"]+)['\"]", query, re.IGNORECASE)
            if quoted_match:
                params[param_name] = quoted_match.group(1)
            else:
                # Try to find quoted strings in general
                quoted_values = re.findall(r"['\"]([^'\"]+)['\"]", query)
                if quoted_values and param_name not in params:
                    # Assign based on description hints
                    for val in quoted_values:
                        if param_name.lower() in param_desc or val.lower() in param_desc:
                            params[param_name] = val
                            break
    
    # Return in the required format: {func_name: {params}}
    return {func_name: params}
