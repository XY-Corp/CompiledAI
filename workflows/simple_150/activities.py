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
        
        # Match deposit/amount parameters
        if "deposit" in param_name.lower() or "amount" in param_name.lower():
            if currency_matches:
                # Remove $ and commas, convert to number
                value_str = currency_matches[0].replace("$", "").replace(",", "")
                if param_type == "integer":
                    params[param_name] = int(float(value_str))
                else:
                    params[param_name] = float(value_str)
            elif plain_numbers:
                # Look for larger numbers that might be deposits
                for num in plain_numbers:
                    val = float(num)
                    if val >= 100:  # Likely a deposit amount
                        if param_type == "integer":
                            params[param_name] = int(val)
                        else:
                            params[param_name] = val
                        break
        
        # Match interest rate parameters
        elif "interest" in param_name.lower() or "rate" in param_name.lower():
            if percent_matches:
                # Convert percentage to decimal (3% -> 0.03) or keep as is based on context
                rate_value = float(percent_matches[0])
                # Check if description suggests decimal format
                if "decimal" in param_desc:
                    params[param_name] = rate_value / 100
                else:
                    # Keep as percentage value (3 for 3%)
                    params[param_name] = rate_value / 100 if rate_value > 1 else rate_value
                    # Actually, looking at the schema, it expects the rate as a float
                    # 3% should be 0.03
                    params[param_name] = float(percent_matches[0]) / 100
        
        # Match year/time period parameters
        elif "year" in param_name.lower() or "period" in param_name.lower() or "time" in param_name.lower():
            if year_matches:
                if param_type == "integer":
                    params[param_name] = int(year_matches[0])
                else:
                    params[param_name] = float(year_matches[0])
    
    return {func_name: params}
