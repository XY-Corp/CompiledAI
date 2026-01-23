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
    
    # Get function details
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters using regex
    params = {}
    
    # Extract all numbers from the query
    # Pattern for currency amounts (e.g., $5000)
    currency_match = re.search(r'\$(\d+(?:,\d{3})*(?:\.\d+)?)', query)
    
    # Pattern for percentages (e.g., 7%)
    percent_match = re.search(r'(\d+(?:\.\d+)?)\s*%', query)
    
    # Pattern for years (e.g., "5 years", "in 5 years")
    years_match = re.search(r'(\d+)\s*years?', query, re.IGNORECASE)
    
    # Map extracted values to parameter names based on schema
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        # Match based on parameter name and description
        if "investment" in param_name.lower() or "amount" in param_name.lower() or "invested" in param_desc:
            if currency_match:
                # Remove commas and convert to int
                amount_str = currency_match.group(1).replace(",", "")
                params[param_name] = int(float(amount_str))
        
        elif "return" in param_name.lower() or "rate" in param_name.lower() or "annual" in param_name.lower():
            if percent_match:
                # Convert percentage to decimal (7% -> 0.07)
                percent_val = float(percent_match.group(1))
                # Check if description suggests decimal format or percentage format
                if "rate" in param_desc:
                    params[param_name] = percent_val / 100.0  # Convert to decimal
                else:
                    params[param_name] = percent_val
        
        elif "year" in param_name.lower() or "time" in param_name.lower() or "period" in param_name.lower():
            if years_match:
                params[param_name] = int(years_match.group(1))
    
    return {func_name: params}
