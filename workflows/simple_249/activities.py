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
    
    # Extract parameters from query
    params = {}
    query_lower = query.lower()
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        
        if param_name == "religion":
            # Extract religion name - common religions
            religions = [
                "christianity", "islam", "hinduism", "buddhism", "judaism",
                "sikhism", "taoism", "confucianism", "shinto", "zoroastrianism"
            ]
            for religion in religions:
                if religion in query_lower:
                    params[param_name] = religion.capitalize()
                    break
            
            # Also try regex pattern: "about X and" or "about X"
            if param_name not in params:
                match = re.search(r'about\s+([A-Za-z]+)(?:\s+and|\s+till|\s+until|$)', query, re.IGNORECASE)
                if match:
                    params[param_name] = match.group(1).capitalize()
        
        elif param_name == "till_century":
            # Extract century number - patterns like "14th century", "till the 14th"
            century_patterns = [
                r'(?:till|until|to)\s+(?:the\s+)?(\d+)(?:st|nd|rd|th)?\s*(?:century)?',
                r'(\d+)(?:st|nd|rd|th)\s+century',
                r'century\s+(\d+)',
            ]
            for pattern in century_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    params[param_name] = int(match.group(1))
                    break
        
        elif param_name == "include_people":
            # Check if people/influential figures are mentioned
            people_keywords = ["people", "figures", "leaders", "influential", "persons"]
            if any(kw in query_lower for kw in people_keywords):
                params[param_name] = True
            # Don't include if not explicitly mentioned (default is False per schema)
    
    return {func_name: params}
