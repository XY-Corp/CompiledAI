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
            # Handle BFCL format: {"question": [[{"role": "user", "content": "..."}]], ...}
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
    
    if not funcs:
        return {"error": "No functions provided"}
    
    func = funcs[0]
    func_name = func.get("name", "")
    props = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters using regex patterns
    params = {}
    query_lower = query.lower()
    
    for param_name, param_info in props.items():
        param_type = param_info.get("type", "string")
        
        if param_name == "address":
            # Extract address - look for patterns like "at <address>" or "located at <address>"
            # Pattern: "at 123 main street" or "located at 123 main street"
            address_match = re.search(r'(?:at|located at)\s+([^,]+?)(?:,|\s+with|\s+in\s+\w+\s+county|$)', query, re.IGNORECASE)
            if address_match:
                params["address"] = address_match.group(1).strip()
        
        elif param_name == "parcel_number":
            # Extract parcel number - look for "parcel number <number>"
            parcel_match = re.search(r'parcel\s+number\s+(\d+)', query, re.IGNORECASE)
            if parcel_match:
                params["parcel_number"] = parcel_match.group(1)
        
        elif param_name == "county":
            # Extract county - look for "in <county> county"
            county_match = re.search(r'in\s+([A-Za-z\s]+?)\s+county', query, re.IGNORECASE)
            if county_match:
                params["county"] = county_match.group(1).strip()
        
        elif param_name == "include_owner":
            # Check if user wants owner information
            if any(phrase in query_lower for phrase in ["include owner", "owner's information", "owners information", "owner info"]):
                params["include_owner"] = True
            else:
                # Use default value if specified
                default_val = param_info.get("default")
                if default_val is not None:
                    params["include_owner"] = default_val
    
    return {func_name: params}
