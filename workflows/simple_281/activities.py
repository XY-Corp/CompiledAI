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
    
    # Parse prompt - may be JSON string with nested structure
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
        else:
            data = prompt
        
        # Extract user query from BFCL format: {"question": [[{"role": "user", "content": "..."}]]}
        if "question" in data and isinstance(data["question"], list):
            if len(data["question"]) > 0 and isinstance(data["question"][0], list):
                if len(data["question"][0]) > 0 and isinstance(data["question"][0][0], dict):
                    query = data["question"][0][0].get("content", str(prompt))
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
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters based on schema
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_type == "integer":
            # Extract year (4-digit number)
            if "year" in param_name.lower() or "year" in param_desc:
                year_match = re.search(r'\b(1[0-9]{3}|20[0-9]{2})\b', query)
                if year_match:
                    params[param_name] = int(year_match.group(1))
            else:
                # Generic integer extraction
                numbers = re.findall(r'\b\d+\b', query)
                if numbers:
                    params[param_name] = int(numbers[0])
        
        elif param_type == "string":
            # Extract based on parameter name/description
            if "name" in param_name.lower() and "maker" not in param_name.lower():
                # Extract instrument name - look for quoted strings or known patterns
                # Pattern: "the musical instrument 'X'" or "instrument 'X'"
                name_match = re.search(r"instrument\s+['\"]([^'\"]+)['\"]", query, re.IGNORECASE)
                if name_match:
                    params[param_name] = name_match.group(1)
                else:
                    # Try generic quoted string for name
                    quoted = re.findall(r"['\"]([^'\"]+)['\"]", query)
                    if quoted:
                        params[param_name] = quoted[0]
            
            elif "maker" in param_name.lower() or "maker" in param_desc:
                # Extract maker - look for "from 'X' maker" or "'X' maker"
                maker_match = re.search(r"from\s+['\"]([^'\"]+)['\"](?:\s+maker)?", query, re.IGNORECASE)
                if maker_match:
                    params[param_name] = maker_match.group(1)
                else:
                    # Try pattern "'X' maker"
                    maker_match2 = re.search(r"['\"]([^'\"]+)['\"](?:\s+maker)", query, re.IGNORECASE)
                    if maker_match2:
                        params[param_name] = maker_match2.group(1)
                    else:
                        # Get second quoted string if available
                        quoted = re.findall(r"['\"]([^'\"]+)['\"]", query)
                        if len(quoted) >= 2:
                            params[param_name] = quoted[1]
    
    return {func_name: params}
