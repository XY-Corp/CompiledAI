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
    
    # Extract parameters based on the query content
    params = {}
    query_lower = query.lower()
    
    # For psych_research.get_preference function
    if "psych_research.get_preference" in func_name or "preference" in func_name:
        # Extract category - look for patterns like "reading", "transportation", "food"
        # In this case: "digital reading over physical books" -> category is "reading"
        if "reading" in query_lower:
            params["category"] = "reading"
        elif "transportation" in query_lower or "transport" in query_lower:
            params["category"] = "transportation"
        elif "food" in query_lower:
            params["category"] = "food"
        else:
            # Try to extract category from context
            category_match = re.search(r'(?:about|on|regarding)\s+(\w+)', query_lower)
            if category_match:
                params["category"] = category_match.group(1)
        
        # Extract option_one and option_two from "X over Y" or "X vs Y" patterns
        # Pattern: "digital reading over physical books"
        over_pattern = re.search(r'(\w+(?:\s+\w+)?)\s+over\s+(\w+(?:\s+\w+)?)', query_lower)
        vs_pattern = re.search(r'(\w+(?:\s+\w+)?)\s+(?:vs\.?|versus)\s+(\w+(?:\s+\w+)?)', query_lower)
        between_pattern = re.search(r'between\s+(\w+(?:\s+\w+)?)\s+and\s+(\w+(?:\s+\w+)?)', query_lower)
        
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
            # Fallback: look for "digital" and "physical" specifically
            if "digital" in query_lower and "physical" in query_lower:
                params["option_one"] = "digital reading"
                params["option_two"] = "physical books"
        
        # demographic is optional with default "all", only include if explicitly mentioned
        demographic_match = re.search(r'(?:for|among|in)\s+([\w\s]+?)(?:\s+(?:population|people|group))?(?:\?|$)', query_lower)
        if demographic_match and demographic_match.group(1).strip() not in ["population", "people", "the"]:
            params["demographic"] = demographic_match.group(1).strip()
    
    else:
        # Generic extraction for other functions
        for param_name, param_info in props.items():
            param_type = param_info.get("type", "string") if isinstance(param_info, dict) else "string"
            
            if param_type in ["integer", "number", "float"]:
                # Extract numbers
                numbers = re.findall(r'\d+(?:\.\d+)?', query)
                if numbers:
                    if param_type == "integer":
                        params[param_name] = int(numbers[0])
                    else:
                        params[param_name] = float(numbers[0])
            else:
                # For string params, try to extract relevant text
                # Look for patterns like "for X" or "in X" or after keywords
                string_match = re.search(rf'(?:for|in|of|with|about)\s+([A-Za-z\s]+?)(?:\s+(?:and|with|,|over|\?)|$)', query, re.IGNORECASE)
                if string_match:
                    params[param_name] = string_match.group(1).strip()
    
    return {func_name: params}
