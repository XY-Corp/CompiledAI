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
    props = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters using regex
    params = {}
    
    # Extract monetary values (present_value): $5000, $5,000, 5000 dollars
    money_patterns = [
        r'\$\s*([\d,]+(?:\.\d+)?)',  # $5000 or $5,000
        r'([\d,]+(?:\.\d+)?)\s*(?:dollars?|USD)',  # 5000 dollars
    ]
    money_value = None
    for pattern in money_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            money_value = int(match.group(1).replace(',', '').split('.')[0])
            break
    
    # Extract interest rate: 5%, 5 percent, interest rate of 5%
    rate_patterns = [
        r'(?:interest\s+rate\s+(?:of\s+)?)?(\d+(?:\.\d+)?)\s*%',  # 5% or interest rate of 5%
        r'(\d+(?:\.\d+)?)\s*percent',  # 5 percent
    ]
    rate_value = None
    for pattern in rate_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            rate_value = float(match.group(1)) / 100.0  # Convert percentage to decimal
            break
    
    # Extract time in years: 3 years, in 3 years
    time_patterns = [
        r'(?:in\s+)?(\d+)\s*years?',  # 3 years or in 3 years
        r'(\d+)\s*(?:year|yr)s?\s+(?:time\s+)?horizon',  # 3 year horizon
    ]
    time_value = None
    for pattern in time_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            time_value = int(match.group(1))
            break
    
    # Extract compounding periods: monthly=12, quarterly=4, annually=1, daily=365
    compounding_map = {
        'daily': 365,
        'weekly': 52,
        'monthly': 12,
        'quarterly': 4,
        'semi-annually': 2,
        'semiannually': 2,
        'annually': 1,
        'yearly': 1,
    }
    compounding_value = None
    for term, periods in compounding_map.items():
        if term in query.lower():
            compounding_value = periods
            break
    
    # Map extracted values to parameter names from schema
    for param_name, param_info in props.items():
        param_type = param_info.get("type", "string")
        
        if param_name == "present_value" and money_value is not None:
            params[param_name] = money_value
        elif param_name == "annual_interest_rate" and rate_value is not None:
            params[param_name] = rate_value
        elif param_name == "time_years" and time_value is not None:
            params[param_name] = time_value
        elif param_name == "compounding_periods_per_year" and compounding_value is not None:
            params[param_name] = compounding_value
    
    return {func_name: params}
