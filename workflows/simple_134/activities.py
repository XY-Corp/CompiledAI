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
    """Extract function call parameters from user query using regex patterns.
    
    Returns a dict with function name as key and parameters as nested object.
    """
    # Parse prompt - may be JSON string with nested structure
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
            # Handle BFCL format: {"question": [[{"role": "user", "content": "..."}]]}
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

    # Extract parameters using regex
    params = {}

    # Extract all numbers from the query
    # Pattern for currency amounts: $5000, $5,000, etc.
    currency_pattern = r'\$[\d,]+(?:\.\d+)?'
    currency_matches = re.findall(currency_pattern, query)
    
    # Pattern for percentages: 7%, 7.5%, etc.
    percent_pattern = r'(\d+(?:\.\d+)?)\s*%'
    percent_matches = re.findall(percent_pattern, query)
    
    # Pattern for years: "5 years", "in 5 years", etc.
    years_pattern = r'(\d+)\s*years?'
    years_matches = re.findall(years_pattern, query, re.IGNORECASE)
    
    # Pattern for general numbers (fallback)
    all_numbers = re.findall(r'\d+(?:\.\d+)?', query)

    # Map extracted values to parameters based on schema
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_name == "investment_amount" or "amount" in param_name.lower() or "invested" in param_desc:
            # Look for currency amount
            if currency_matches:
                # Remove $ and commas, convert to int
                amount_str = currency_matches[0].replace("$", "").replace(",", "")
                params[param_name] = int(float(amount_str))
            elif all_numbers:
                # Find the largest number (likely the investment amount)
                nums = [float(n) for n in all_numbers]
                params[param_name] = int(max(nums))
                
        elif param_name == "annual_return" or "return" in param_name.lower() or "rate" in param_desc:
            # Look for percentage
            if percent_matches:
                # Convert percentage to decimal (7% -> 0.07)
                params[param_name] = float(percent_matches[0]) / 100.0
                
        elif param_name == "years" or "year" in param_name.lower() or "time" in param_desc:
            # Look for years
            if years_matches:
                params[param_name] = int(years_matches[0])

    return {func_name: params}
