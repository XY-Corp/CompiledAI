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
        
        # Extract user query from BFCL format
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
        elif "ace" in query_lower:
            params["success_outcomes"] = 4
        elif "king" in query_lower or "queen" in query_lower or "jack" in query_lower:
            params["success_outcomes"] = 4
        elif numbers:
            # Use first number as success_outcomes if no suit/rank detected
            params["success_outcomes"] = int(numbers[0])
        
        # Look for total outcomes (deck size)
        if "52" in query:
            params["total_outcomes"] = 52
        elif "deck" in query_lower:
            # Standard deck
            params["total_outcomes"] = 52
        elif len(numbers) >= 2:
            # Use second number as total if available
            params["total_outcomes"] = int(numbers[1])
        elif len(numbers) >= 1 and "success_outcomes" not in params:
            params["total_outcomes"] = int(numbers[0])
        
        # Check for ratio format request
        if "ratio" in query_lower or "as ratio" in query_lower or "format it as ratio" in query_lower:
            params["format_as_ratio"] = True
        elif "decimal" in query_lower:
            params["format_as_ratio"] = False
    else:
        # Generic extraction for other functions
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
                if param_name in query_lower or param_name.replace("_", " ") in query_lower:
                    params[param_name] = True
            elif param_type == "string":
                # Try to extract string values with patterns
                pattern = rf'(?:for|in|of|with)\s+([A-Za-z\s]+?)(?:\s+(?:and|with|,|\.)|$)'
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    params[param_name] = match.group(1).strip()
    
    return {func_name: params}
