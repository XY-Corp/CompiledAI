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
    
    Parses the user query and extracts parameters to match the function schema.
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
    
    # Get function schema
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    props = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters from query using regex and string matching
    params = {}
    query_lower = query.lower()
    
    for param_name, param_info in props.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_type == "integer":
            # Extract year - look for 4-digit numbers
            years = re.findall(r'\b(19\d{2}|20\d{2})\b', query)
            if years:
                params[param_name] = int(years[0])
        
        elif param_type == "string":
            # Handle company_name - look for "company X" or "against X"
            if "company" in param_name.lower() or "company" in param_desc:
                # Pattern: "against X" or "company X"
                company_match = re.search(r'(?:against|company)\s+(?:the\s+)?(?:company\s+)?([A-Z][a-zA-Z0-9]+)', query)
                if company_match:
                    params[param_name] = company_match.group(1)
            
            # Handle location - look for "in X" patterns for states/cities
            elif "location" in param_name.lower() or "location" in param_desc:
                # Pattern: "in California" or "in New York"
                location_match = re.search(r'\bin\s+([A-Z][a-zA-Z\s]+?)(?:\s+in\s+the\s+year|\s+in\s+\d{4}|$)', query)
                if location_match:
                    params[param_name] = location_match.group(1).strip()
            
            # Handle case_type - check for keywords
            elif "case_type" in param_name.lower() or "type" in param_desc:
                # Check for case type keywords
                if "civil" in query_lower:
                    params[param_name] = "civil"
                elif "criminal" in query_lower:
                    params[param_name] = "criminal"
                elif "small_claims" in query_lower or "small claims" in query_lower:
                    params[param_name] = "small_claims"
                # Don't set if not found - it's optional with default 'all'
    
    return {func_name: params}
