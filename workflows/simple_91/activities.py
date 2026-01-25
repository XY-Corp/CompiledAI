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
    # Parse prompt - may be JSON string with nested structure
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
        else:
            data = prompt
        
        # Extract user query from BFCL format: {"question": [[{"role": "user", "content": "..."}]]}
        if isinstance(data, dict) and "question" in data:
            question_data = data["question"]
            if isinstance(question_data, list) and len(question_data) > 0:
                if isinstance(question_data[0], list) and len(question_data[0]) > 0:
                    query = question_data[0][0].get("content", str(prompt))
                else:
                    query = str(prompt)
            else:
                query = str(prompt)
        else:
            query = str(prompt)
    except (json.JSONDecodeError, TypeError):
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
    func_name = func.get("name", "unknown")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters using regex and string matching
    params = {}
    query_lower = query.lower()
    
    for param_name, param_info in params_schema.items():
        param_desc = param_info.get("description", "").lower()
        
        if param_name == "cuisine":
            # Extract cuisine type - look for common cuisine words
            cuisine_patterns = [
                r'\b(sushi|japanese|chinese|italian|mexican|indian|thai|french|korean|vietnamese|american|greek|mediterranean|spanish|german)\b'
            ]
            for pattern in cuisine_patterns:
                match = re.search(pattern, query_lower)
                if match:
                    params["cuisine"] = match.group(1)
                    break
        
        elif param_name == "location":
            # Extract city/location - look for "in [City]" pattern or known cities
            location_patterns = [
                r'\bin\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)?)',  # "in Boston", "in New York"
                r'\b(Boston|New York|Los Angeles|Chicago|Houston|Phoenix|Philadelphia|San Antonio|San Diego|Dallas|San Jose|Austin|Jacksonville|Fort Worth|Columbus|Charlotte|Seattle|Denver|Washington|Nashville)\b'
            ]
            for pattern in location_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    params["location"] = match.group(1).strip()
                    break
        
        elif param_name == "condition":
            # Extract condition - look for day-related or amenity-related phrases
            condition_patterns = [
                r'(?:that\s+)?opens?\s+on\s+(\w+days?)',  # "opens on Sundays"
                r'(?:that\s+)?is\s+open\s+on\s+(\w+days?)',  # "is open on Sundays"
                r'open\s+on\s+(\w+)',  # "open on Sunday"
                r'(?:that\s+)?has\s+(.+?)(?:\.|$)',  # "that has outdoor seating"
                r'with\s+(.+?)(?:\.|$)',  # "with parking"
            ]
            for pattern in condition_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    condition_value = match.group(1).strip()
                    # Normalize: "Sundays" -> "opens on Sundays"
                    if re.match(r'\w+days?$', condition_value, re.IGNORECASE):
                        params["condition"] = f"opens on {condition_value}"
                    else:
                        params["condition"] = condition_value
                    break
    
    return {func_name: params}
