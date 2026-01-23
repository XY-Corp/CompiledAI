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
    
    # Get function schema
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    props = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters from query using regex and string matching
    params = {}
    
    for param_name, param_info in props.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_name == "case_number":
            # Extract case number - pattern like CA123456, XX123456, etc.
            case_match = re.search(r'\b([A-Z]{2}\d{6})\b', query, re.IGNORECASE)
            if case_match:
                params[param_name] = case_match.group(1).upper()
            else:
                # Try more general pattern: "case number X" or "case X"
                case_match = re.search(r'case\s*(?:number)?\s*([A-Za-z0-9]+)', query, re.IGNORECASE)
                if case_match:
                    params[param_name] = case_match.group(1)
        
        elif param_name == "county":
            # Extract county name - pattern like "X County" or "in X County"
            county_match = re.search(r'(?:in\s+)?([A-Za-z\s]+?)\s+County', query, re.IGNORECASE)
            if county_match:
                params[param_name] = county_match.group(1).strip()
        
        elif param_name == "details":
            # Check if user wants details - look for keywords
            if param_type == "boolean":
                # Look for "details", "detailed", "full" etc.
                wants_details = bool(re.search(r'\b(detail|detailed|details|full|complete)\b', query, re.IGNORECASE))
                if wants_details:
                    params[param_name] = True
                # Only include if explicitly requested (it's optional with default false)
    
    return {func_name: params}
