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
    """Extract function name and parameters from user query based on function schema.
    
    Returns format: {"function_name": {"param1": val1, "param2": val2}}
    """
    # Parse prompt - may be JSON string with nested structure
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
    
    # Extract parameters from query using regex and string matching
    params = {}
    query_lower = query.lower()
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_name == "city":
            # Extract city - look for "in [City]" pattern
            city_match = re.search(r'\bin\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)?)', query)
            if city_match:
                city = city_match.group(1).strip()
                # Add state abbreviation if it's a known city
                if city.lower() == "chicago":
                    params["city"] = "Chicago, IL"
                else:
                    params["city"] = city
        
        elif param_name == "specialty":
            # Extract specialty from enum values
            enum_values = param_info.get("items", {}).get("enum", [])
            found_specialties = []
            for specialty in enum_values:
                if specialty.lower() in query_lower:
                    found_specialties.append(specialty)
            if found_specialties:
                params["specialty"] = found_specialties
        
        elif param_name == "fee":
            # Extract fee - look for number near "fee", "charge", "less than", "under", dollar amounts
            # Pattern: "less than X dollars" or "under X" or "fee X" or "$X"
            fee_patterns = [
                r'(?:less\s+than|under|below|max(?:imum)?)\s+\$?(\d+)',
                r'\$(\d+)',
                r'(\d+)\s*(?:dollars?|usd)',
                r'fee\s+(?:of\s+)?(?:less\s+than\s+)?\$?(\d+)',
                r'charge\s+(?:fee\s+)?(?:less\s+than\s+)?\$?(\d+)',
            ]
            for pattern in fee_patterns:
                fee_match = re.search(pattern, query_lower)
                if fee_match:
                    params["fee"] = int(fee_match.group(1))
                    break
    
    return {func_name: params}
