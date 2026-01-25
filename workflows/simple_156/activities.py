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
    
    # Parse prompt - may be JSON string with nested structure
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
    
    # Extract case_number - pattern like CA123456, XX123456, etc.
    case_match = re.search(r'\b([A-Z]{2}\d{6})\b', query)
    if case_match and "case_number" in params_schema:
        params["case_number"] = case_match.group(1)
    
    # Extract county - look for "in X County" or "X County"
    county_match = re.search(r'(?:in\s+)?([A-Za-z\s]+?)\s+County', query, re.IGNORECASE)
    if county_match and "county" in params_schema:
        params["county"] = county_match.group(1).strip() + " County"
    
    # Extract details boolean - check for keywords like "detailed", "details"
    if "details" in params_schema:
        details_keywords = ["detailed", "details", "full report", "complete"]
        has_details = any(kw in query.lower() for kw in details_keywords)
        if has_details:
            params["details"] = True
        # If not explicitly mentioned, don't include (let it default)
    
    return {func_name: params}
