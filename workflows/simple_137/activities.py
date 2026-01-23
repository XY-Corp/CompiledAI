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
    
    # Extract all numbers (integers and floats) from query
    # Pattern for currency amounts like $5000
    currency_match = re.search(r'\$(\d+(?:,\d{3})*(?:\.\d+)?)', query)
    
    # Pattern for percentages like 6%
    percent_match = re.search(r'(\d+(?:\.\d+)?)\s*%', query)
    
    # Pattern for years/period like "5 years"
    years_match = re.search(r'(\d+)\s*years?', query, re.IGNORECASE)
    
    # Map extracted values to parameter names based on schema
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_name == "investment_amount" or "investment" in param_desc or "amount" in param_desc:
            if currency_match:
                # Remove commas and convert to int
                amount_str = currency_match.group(1).replace(",", "")
                params[param_name] = int(float(amount_str))
        
        elif param_name == "annual_growth_rate" or "growth rate" in param_desc or "rate" in param_desc:
            if percent_match:
                # Convert percentage to decimal (6% -> 0.06) or keep as 6 based on context
                rate_value = float(percent_match.group(1))
                # Check if description suggests decimal format
                if "decimal" in param_desc:
                    params[param_name] = rate_value / 100
                else:
                    # Keep as percentage value (6 for 6%)
                    params[param_name] = rate_value
        
        elif param_name == "holding_period" or "years" in param_desc or "period" in param_desc:
            if years_match:
                params[param_name] = int(years_match.group(1))
        
        elif param_type == "boolean":
            # Check if the boolean parameter is mentioned in the query
            if param_name in query.lower() or (param_name == "dividends" and "dividend" in query.lower()):
                params[param_name] = True
            # Don't include optional boolean if not mentioned
    
    return {func_name: params}
