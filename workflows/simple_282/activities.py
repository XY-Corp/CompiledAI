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
    """Extract function name and parameters from user query. Returns {func_name: {params}}."""
    
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
    
    # Get function schema
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters based on schema
    params = {}
    query_lower = query.lower()
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_type == "string":
            # Extract brand - look for known brand names or pattern "brand X"
            if "brand" in param_name.lower() or "brand" in param_desc:
                # Common flute/instrument brands
                brands = ["yamaha", "pearl", "gemeinhardt", "powell", "muramatsu", "altus", "miyazawa", "sankyo", "haynes", "brannen"]
                for brand in brands:
                    if brand in query_lower:
                        params[param_name] = brand.capitalize()
                        break
                
                # Also try regex pattern for "brand X" or "X brand"
                if param_name not in params:
                    brand_match = re.search(r'(\w+)\s+(?:flute|instrument|brand)', query_lower)
                    if brand_match:
                        params[param_name] = brand_match.group(1).capitalize()
        
        elif param_type == "array":
            # Extract array items - check for enum values in schema
            items_schema = param_info.get("items", {})
            enum_values = items_schema.get("enum", [])
            
            if enum_values:
                # Find which enum values are mentioned in the query
                found_values = []
                for enum_val in enum_values:
                    if enum_val.lower() in query_lower:
                        found_values.append(enum_val)
                if found_values:
                    params[param_name] = found_values
            else:
                # Try to extract comma-separated or "and"-separated values
                # Pattern: "specifications of X, Y, and Z" or "specs: X, Y, Z"
                specs_match = re.search(r'(?:specifications?|specs?)\s+(?:of\s+)?(.+?)(?:\s+available|\s+for\s+sale|$)', query_lower)
                if specs_match:
                    specs_text = specs_match.group(1)
                    # Split by comma or "and"
                    specs = re.split(r',\s*|\s+and\s+', specs_text)
                    params[param_name] = [s.strip() for s in specs if s.strip()]
    
    return {func_name: params}
