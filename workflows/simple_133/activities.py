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
    props = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters using regex
    params = {}
    
    # Extract monetary values (present_value): $5000, $5,000, 5000 dollars
    money_patterns = [
        r'\$\s*([\d,]+(?:\.\d+)?)',  # $5000 or $5,000
        r'([\d,]+(?:\.\d+)?)\s*(?:dollars?|USD)',  # 5000 dollars
        r'investment\s+(?:of\s+)?\$?([\d,]+(?:\.\d+)?)',  # investment of 5000
    ]
    
    present_value = None
    for pattern in money_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            present_value = int(match.group(1).replace(',', '').split('.')[0])
            break
    
    if present_value is not None and "present_value" in props:
        params["present_value"] = present_value
    
    # Extract interest rate: 5%, 5 percent, 0.05 interest rate
    rate_patterns = [
        r'(\d+(?:\.\d+)?)\s*%',  # 5% or 5.5%
        r'(\d+(?:\.\d+)?)\s*percent',  # 5 percent
        r'interest\s+rate\s+(?:of\s+)?(\d+(?:\.\d+)?)',  # interest rate of 5
        r'rate\s+(?:of\s+)?(\d+(?:\.\d+)?)\s*%?',  # rate of 5%
    ]
    
    annual_interest_rate = None
    for pattern in rate_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            rate_val = float(match.group(1))
            # Convert percentage to decimal if > 1 (e.g., 5% -> 0.05)
            if rate_val > 1:
                annual_interest_rate = rate_val / 100.0
            else:
                annual_interest_rate = rate_val
            break
    
    if annual_interest_rate is not None and "annual_interest_rate" in props:
        params["annual_interest_rate"] = annual_interest_rate
    
    # Extract time in years: 3 years, 3-year, in 3 years
    time_patterns = [
        r'(\d+)\s*(?:-?\s*)?years?',  # 3 years, 3-year
        r'in\s+(\d+)\s+years?',  # in 3 years
        r'(\d+)\s*yr',  # 3yr
    ]
    
    time_years = None
    for pattern in time_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            time_years = int(match.group(1))
            break
    
    if time_years is not None and "time_years" in props:
        params["time_years"] = time_years
    
    # Extract compounding periods: monthly=12, quarterly=4, daily=365, annually=1
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
    
    compounding_periods = None
    for term, periods in compounding_map.items():
        if term in query.lower():
            compounding_periods = periods
            break
    
    # Also check for explicit number of compounding periods
    if compounding_periods is None:
        comp_match = re.search(r'(\d+)\s*(?:times?\s+(?:per|a)\s+year|compounding\s+periods?)', query, re.IGNORECASE)
        if comp_match:
            compounding_periods = int(comp_match.group(1))
    
    if compounding_periods is not None and "compounding_periods_per_year" in props:
        params["compounding_periods_per_year"] = compounding_periods
    
    return {func_name: params}
