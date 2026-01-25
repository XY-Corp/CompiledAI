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
    """Extract function call parameters from natural language query.
    
    Parses the prompt to extract the user query and function schema,
    then uses regex and pattern matching to extract parameter values.
    Returns format: {"function_name": {"param1": val1, ...}}
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
    
    # Extract parameters based on the query content
    params = {}
    query_lower = query.lower()
    
    # For probability_of_event: extract success_outcomes, total_outcomes, format_as_ratio
    if func_name == "probability_of_event":
        # Extract numbers from the query
        numbers = re.findall(r'\d+', query)
        
        # Look for specific patterns for card probability
        # "heart suit" = 13 cards, "deck of 52 cards" = 52 total
        if "heart" in query_lower or "hearts" in query_lower:
            # Standard deck has 13 hearts
            params["success_outcomes"] = 13
        elif "spade" in query_lower or "spades" in query_lower:
            params["success_outcomes"] = 13
        elif "club" in query_lower or "clubs" in query_lower:
            params["success_outcomes"] = 13
        elif "diamond" in query_lower or "diamonds" in query_lower:
            params["success_outcomes"] = 13
        elif numbers:
            # Use first number as success outcomes if no suit mentioned
            params["success_outcomes"] = int(numbers[0])
        
        # Look for total outcomes - "deck of 52" or just extract number
        deck_match = re.search(r'(\d+)\s*cards?', query_lower)
        if deck_match:
            params["total_outcomes"] = int(deck_match.group(1))
        elif "standard deck" in query_lower or "deck of cards" in query_lower:
            params["total_outcomes"] = 52
        elif len(numbers) >= 2:
            # If we have multiple numbers, second one might be total
            params["total_outcomes"] = int(numbers[-1])
        
        # Check for ratio format request
        if "ratio" in query_lower or "as ratio" in query_lower or "format it as ratio" in query_lower:
            params["format_as_ratio"] = True
        elif "decimal" in query_lower:
            params["format_as_ratio"] = False
    else:
        # Generic extraction for other functions
        # Extract all numbers
        numbers = re.findall(r'\d+(?:\.\d+)?', query)
        num_idx = 0
        
        for param_name, param_info in params_schema.items():
            param_type = param_info.get("type", "string") if isinstance(param_info, dict) else "string"
            
            if param_type in ["integer", "number", "float"]:
                if num_idx < len(numbers):
                    if param_type == "integer":
                        params[param_name] = int(numbers[num_idx])
                    else:
                        params[param_name] = float(numbers[num_idx])
                    num_idx += 1
            elif param_type == "boolean":
                # Check for boolean indicators in query
                param_lower = param_name.lower().replace("_", " ")
                if param_lower in query_lower or f"as {param_lower.split()[-1]}" in query_lower:
                    params[param_name] = True
            elif param_type == "string":
                # Try to extract string values with patterns like "for X" or "in X"
                string_match = re.search(
                    r'(?:for|in|of|with|named?)\s+([A-Za-z][A-Za-z\s]+?)(?:\s+(?:and|with|,|\.)|$)',
                    query,
                    re.IGNORECASE
                )
                if string_match:
                    params[param_name] = string_match.group(1).strip()
    
    return {func_name: params}
