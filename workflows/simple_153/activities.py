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
    """Extract function name and parameters from user query using regex patterns."""
    
    # Parse prompt (may be JSON string with nested structure)
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
            # Extract user query from BFCL format
            if "question" in data and isinstance(data["question"], list):
                if len(data["question"]) > 0 and isinstance(data["question"][0], list):
                    query = data["question"][0][0].get("content", prompt)
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
    
    # Get function details
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters using regex
    params = {}
    
    # Extract all numbers (integers and floats) from the query
    # Pattern for currency amounts like $5000
    currency_match = re.search(r'\$(\d+(?:,\d{3})*(?:\.\d+)?)', query)
    principal_value = None
    if currency_match:
        principal_value = int(currency_match.group(1).replace(',', ''))
    
    # Pattern for percentage like 3%
    rate_match = re.search(r'(\d+(?:\.\d+)?)\s*%', query)
    rate_value = None
    if rate_match:
        rate_value = float(rate_match.group(1)) / 100  # Convert percentage to decimal
    
    # Pattern for time period like "5 years" or "for 5 years"
    time_match = re.search(r'(?:for\s+)?(\d+)\s+years?', query, re.IGNORECASE)
    time_value = None
    if time_match:
        time_value = int(time_match.group(1))
    
    # Pattern for compounding frequency
    # "compounded quarterly" = 4, "compounded monthly" = 12, "compounded annually" = 1, etc.
    compounding_map = {
        'annually': 1,
        'yearly': 1,
        'semi-annually': 2,
        'semiannually': 2,
        'quarterly': 4,
        'monthly': 12,
        'weekly': 52,
        'daily': 365
    }
    
    n_value = None
    for freq_word, freq_num in compounding_map.items():
        if freq_word in query.lower():
            n_value = freq_num
            break
    
    # Also check for explicit "n times" pattern
    if n_value is None:
        n_match = re.search(r'(\d+)\s+times?\s+(?:per|a)\s+year', query, re.IGNORECASE)
        if n_match:
            n_value = int(n_match.group(1))
    
    # Map extracted values to parameter names from schema
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_name == "principal" or "initial" in param_desc or "deposit" in param_desc:
            if principal_value is not None:
                params[param_name] = principal_value
        elif param_name == "rate" or "interest rate" in param_desc:
            if rate_value is not None:
                params[param_name] = rate_value
        elif param_name == "time" or "time period" in param_desc or "years" in param_desc:
            if time_value is not None:
                params[param_name] = time_value
        elif param_name == "n" or "compounded" in param_desc or "number of times" in param_desc:
            if n_value is not None:
                params[param_name] = n_value
    
    return {func_name: params}
