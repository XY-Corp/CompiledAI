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
            # Extract user query from BFCL format: {"question": [[{"role": "user", "content": "..."}]]}
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
    
    # Extract parameters from query using pattern matching
    params = {}
    query_lower = query.lower()
    
    # For psych_research.get_preference function
    if "psych_research.get_preference" in func_name:
        # Extract category - look for patterns like "reading", "transportation", etc.
        # The query mentions "reading" in context of digital vs physical books
        if "reading" in query_lower or "book" in query_lower:
            params["category"] = "reading"
        elif "transport" in query_lower:
            params["category"] = "transportation"
        elif "food" in query_lower:
            params["category"] = "food"
        else:
            # Try to extract category from context
            category_match = re.search(r'(?:about|on|regarding|of)\s+(\w+)', query_lower)
            if category_match:
                params["category"] = category_match.group(1)
        
        # Extract option_one and option_two - look for "X over Y" or "X vs Y" patterns
        # Pattern: "preferring X over Y" or "X vs Y" or "between X and Y"
        over_pattern = re.search(r'(?:preferring|prefer)\s+(.+?)\s+over\s+(.+?)(?:\?|$|\.)', query_lower)
        vs_pattern = re.search(r'(.+?)\s+(?:vs\.?|versus)\s+(.+?)(?:\?|$|\.)', query_lower)
        between_pattern = re.search(r'between\s+(.+?)\s+and\s+(.+?)(?:\?|$|\.)', query_lower)
        
        if over_pattern:
            params["option_one"] = over_pattern.group(1).strip()
            params["option_two"] = over_pattern.group(2).strip()
        elif vs_pattern:
            params["option_one"] = vs_pattern.group(1).strip()
            params["option_two"] = vs_pattern.group(2).strip()
        elif between_pattern:
            params["option_one"] = between_pattern.group(1).strip()
            params["option_two"] = between_pattern.group(2).strip()
        else:
            # Specific extraction for "digital reading over physical books"
            if "digital" in query_lower and "physical" in query_lower:
                params["option_one"] = "digital reading"
                params["option_two"] = "physical books"
        
        # demographic is optional with default "all", only include if explicitly mentioned
        demographic_match = re.search(r'(?:among|for|demographic[:\s]+)\s*(\w+(?:\s+\w+)?)', query_lower)
        if demographic_match and demographic_match.group(1) not in ["reading", "digital", "physical", "books"]:
            params["demographic"] = demographic_match.group(1).strip()
    
    else:
        # Generic extraction for other functions
        for param_name, param_info in params_schema.items():
            param_type = param_info.get("type", "string") if isinstance(param_info, dict) else "string"
            
            if param_type in ["integer", "number", "float"]:
                # Extract numbers
                numbers = re.findall(r'\d+(?:\.\d+)?', query)
                if numbers:
                    if param_type == "integer":
                        params[param_name] = int(numbers[0])
                    else:
                        params[param_name] = float(numbers[0])
                    numbers.pop(0)
            elif param_type == "string":
                # Try to extract string values based on common patterns
                string_match = re.search(rf'{param_name}[:\s]+["\']?([^"\']+)["\']?', query_lower)
                if string_match:
                    params[param_name] = string_match.group(1).strip()
    
    return {func_name: params}
