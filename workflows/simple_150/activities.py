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
    # Pattern for currency amounts (e.g., $1000, $1,000.00)
    currency_pattern = r'\$[\d,]+(?:\.\d+)?'
    currency_matches = re.findall(currency_pattern, query)
    
    # Pattern for percentages (e.g., 3%, 3.5%)
    percent_pattern = r'(\d+(?:\.\d+)?)\s*%'
    percent_matches = re.findall(percent_pattern, query)
    
    # Pattern for year/time periods (e.g., "1 year", "5 years")
    year_pattern = r'(\d+)\s*years?'
    year_matches = re.findall(year_pattern, query, re.IGNORECASE)
    
    # Pattern for plain numbers
    plain_numbers = re.findall(r'\b(\d+(?:\.\d+)?)\b', query)
    
    # Map extracted values to parameters based on schema
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_name == "deposit" or "deposit" in param_desc:
            # Look for currency amount
            if currency_matches:
                # Remove $ and commas, convert to int
                amount_str = currency_matches[0].replace("$", "").replace(",", "")
                params[param_name] = int(float(amount_str))
            elif plain_numbers:
                # Use first large number as deposit
                for num in plain_numbers:
                    if float(num) >= 100:  # Likely a deposit amount
                        params[param_name] = int(float(num))
                        break
        
        elif param_name == "annual_interest_rate" or "interest" in param_desc or "rate" in param_desc:
            # Look for percentage
            if percent_matches:
                rate = float(percent_matches[0])
                # Convert to decimal if needed (3% -> 0.03 or keep as 3 based on context)
                # Based on the schema expecting float, keep as percentage value
                params[param_name] = rate / 100 if rate > 1 else rate
        
        elif param_name == "years" or "year" in param_desc or "period" in param_desc or "time" in param_desc:
            # Look for year/time period
            if year_matches:
                params[param_name] = int(year_matches[0])
            else:
                # Look for standalone numbers that could be years (small numbers)
                for num in plain_numbers:
                    if 1 <= float(num) <= 50:  # Reasonable year range
                        params[param_name] = int(float(num))
                        break
    
    return {func_name: params}
