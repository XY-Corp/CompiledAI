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
    """Extract function call parameters from user query using regex patterns."""
    
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
    
    # Get function schema
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters using regex
    params = {}
    
    # Extract monetary values (present_value) - look for $ amounts
    money_patterns = [
        r'\$\s*([\d,]+(?:\.\d+)?)',  # $5000 or $5,000 or $5000.00
        r'([\d,]+(?:\.\d+)?)\s*(?:dollar|usd)',  # 5000 dollars
        r'investment\s+(?:of\s+)?\$?([\d,]+(?:\.\d+)?)',  # investment of $5000
    ]
    
    for pattern in money_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            value_str = match.group(1).replace(',', '')
            params["present_value"] = int(float(value_str))
            break
    
    # Extract interest rate - look for percentage
    rate_patterns = [
        r'(\d+(?:\.\d+)?)\s*%',  # 5% or 5.5%
        r'interest\s+rate\s+(?:of\s+)?(\d+(?:\.\d+)?)',  # interest rate of 5
        r'rate\s+(?:of\s+)?(\d+(?:\.\d+)?)\s*%?',  # rate of 5%
    ]
    
    for pattern in rate_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            rate_value = float(match.group(1))
            # Convert percentage to decimal (5% -> 0.05)
            if rate_value > 1:
                rate_value = rate_value / 100
            params["annual_interest_rate"] = rate_value
            break
    
    # Extract years/term
    years_patterns = [
        r'(\d+)\s*years?',  # 10 years
        r'term\s+(?:of\s+)?(\d+)',  # term of 10
        r'for\s+(\d+)\s*(?:years?|yrs?)',  # for 10 years
        r'(\d+)\s*(?:year|yr)\s+(?:term|period)',  # 10 year term
    ]
    
    for pattern in years_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            params["years"] = int(match.group(1))
            break
    
    # Extract compounds_per_year if mentioned (optional parameter)
    compound_patterns = [
        r'compound(?:ed|ing)?\s+(\w+)',  # compounded monthly/quarterly/annually
        r'(\d+)\s+times?\s+(?:per|a)\s+year',  # 12 times per year
    ]
    
    compound_mapping = {
        'annually': 1, 'annual': 1, 'yearly': 1,
        'semi-annually': 2, 'semiannually': 2,
        'quarterly': 4,
        'monthly': 12,
        'weekly': 52,
        'daily': 365,
    }
    
    for pattern in compound_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            value = match.group(1).lower()
            if value in compound_mapping:
                params["compounds_per_year"] = compound_mapping[value]
            elif value.isdigit():
                params["compounds_per_year"] = int(value)
            break
    
    return {func_name: params}
