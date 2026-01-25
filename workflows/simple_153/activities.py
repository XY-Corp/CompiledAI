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
                    query = str(data["question"])
            else:
                query = str(prompt)
        else:
            query = str(prompt)
    except (json.JSONDecodeError, TypeError):
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
    
    # Extract all numbers from the query
    # Pattern for currency amounts (e.g., $5000)
    currency_match = re.search(r'\$(\d+(?:,\d{3})*(?:\.\d+)?)', query)
    
    # Pattern for percentages (e.g., 3%)
    percent_match = re.search(r'(\d+(?:\.\d+)?)\s*%', query)
    
    # Pattern for years/time periods (e.g., "5 years", "for 5 years")
    time_match = re.search(r'(?:for\s+)?(\d+)\s+years?', query, re.IGNORECASE)
    
    # Pattern for compounding frequency
    # Map common terms to their numeric values
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
    
    compounding_freq = None
    for term, value in compounding_map.items():
        if term in query.lower():
            compounding_freq = value
            break
    
    # Map extracted values to parameter names based on schema
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_name == "principal" or "initial" in param_desc or "deposit" in param_desc:
            if currency_match:
                # Remove commas and convert to int
                value = currency_match.group(1).replace(",", "")
                params[param_name] = int(float(value))
        
        elif param_name == "rate" or "interest rate" in param_desc:
            if percent_match:
                # Convert percentage to decimal (3% -> 0.03)
                params[param_name] = float(percent_match.group(1)) / 100
        
        elif param_name == "time" or "time period" in param_desc or "years" in param_desc:
            if time_match:
                params[param_name] = int(time_match.group(1))
        
        elif param_name == "n" or "compounded" in param_desc or "number of times" in param_desc:
            if compounding_freq is not None:
                params[param_name] = compounding_freq
    
    return {func_name: params}
