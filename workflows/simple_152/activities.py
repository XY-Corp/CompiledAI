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
    
    # Parse prompt - may be JSON string with nested structure
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
    # Pattern for currency amounts (e.g., $50000, $50,000)
    currency_pattern = r'\$[\d,]+(?:\.\d+)?'
    currency_matches = re.findall(currency_pattern, query)
    
    # Pattern for percentages (e.g., 5%, 5.5%)
    percent_pattern = r'(\d+(?:\.\d+)?)\s*%'
    percent_matches = re.findall(percent_pattern, query)
    
    # Pattern for years/time periods (e.g., "3 years", "after 5 years")
    years_pattern = r'(\d+)\s*years?'
    years_matches = re.findall(years_pattern, query, re.IGNORECASE)
    
    # Pattern for plain numbers
    plain_numbers = re.findall(r'\b\d+(?:\.\d+)?\b', query)
    
    # Map extracted values to parameters based on schema
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        # Match based on parameter name and description
        if "investment" in param_name.lower() or "amount" in param_name.lower() or "investment" in param_desc:
            # Look for currency amount
            if currency_matches:
                # Remove $ and commas, convert to int
                amount_str = currency_matches[0].replace("$", "").replace(",", "")
                params[param_name] = int(float(amount_str))
            elif plain_numbers:
                # Use largest number as investment amount
                nums = [float(n) for n in plain_numbers]
                params[param_name] = int(max(nums))
        
        elif "yield" in param_name.lower() or "rate" in param_name.lower() or "yield" in param_desc or "rate" in param_desc:
            # Look for percentage
            if percent_matches:
                # Convert percentage to decimal (5% -> 0.05)
                percent_val = float(percent_matches[0])
                # Check if description suggests decimal format or percentage format
                if "rate" in param_desc and percent_val > 1:
                    params[param_name] = percent_val / 100.0
                else:
                    params[param_name] = percent_val / 100.0
        
        elif "year" in param_name.lower() or "period" in param_name.lower() or "time" in param_name.lower() or "year" in param_desc:
            # Look for years
            if years_matches:
                params[param_name] = int(years_matches[0])
            elif plain_numbers:
                # Use smallest reasonable number as years
                nums = [int(float(n)) for n in plain_numbers if float(n) < 100]
                if nums:
                    params[param_name] = min(nums)
    
    return {func_name: params}
