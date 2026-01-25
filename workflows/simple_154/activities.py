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
    
    # Get function details
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters using regex
    params = {}
    
    # Extract monetary values (present_value) - look for $ amounts
    # Pattern: $5000, $5,000, $5000.00
    money_match = re.search(r'\$\s*([\d,]+(?:\.\d+)?)', query)
    if money_match and "present_value" in params_schema:
        value_str = money_match.group(1).replace(',', '')
        params["present_value"] = int(float(value_str))
    
    # Extract years/term - look for "X years" or "term of X years"
    years_patterns = [
        r'(?:term\s+of\s+)?(\d+)\s*years?',
        r'for\s+(\d+)\s*years?',
        r'(\d+)\s*year\s+term',
    ]
    for pattern in years_patterns:
        years_match = re.search(pattern, query, re.IGNORECASE)
        if years_match and "years" in params_schema:
            params["years"] = int(years_match.group(1))
            break
    
    # Extract interest rate - look for "X%" or "X percent"
    # Pattern: 5%, 5.5%, 5 percent
    rate_patterns = [
        r'(\d+(?:\.\d+)?)\s*%',
        r'(\d+(?:\.\d+)?)\s*percent',
        r'interest\s+rate\s+of\s+(\d+(?:\.\d+)?)',
        r'rate\s+of\s+(\d+(?:\.\d+)?)',
    ]
    for pattern in rate_patterns:
        rate_match = re.search(pattern, query, re.IGNORECASE)
        if rate_match and "annual_interest_rate" in params_schema:
            # Convert percentage to decimal (5% -> 0.05)
            rate_value = float(rate_match.group(1))
            params["annual_interest_rate"] = rate_value / 100.0
            break
    
    # Extract compounds_per_year if mentioned (optional parameter)
    compound_patterns = [
        r'compounded\s+(\w+)',
        r'(\d+)\s+times?\s+(?:per|a)\s+year',
    ]
    compound_mapping = {
        'annually': 1,
        'yearly': 1,
        'semi-annually': 2,
        'semiannually': 2,
        'quarterly': 4,
        'monthly': 12,
        'weekly': 52,
        'daily': 365,
    }
    for pattern in compound_patterns:
        compound_match = re.search(pattern, query, re.IGNORECASE)
        if compound_match and "compounds_per_year" in params_schema:
            matched_value = compound_match.group(1).lower()
            if matched_value in compound_mapping:
                params["compounds_per_year"] = compound_mapping[matched_value]
            elif matched_value.isdigit():
                params["compounds_per_year"] = int(matched_value)
            break
    
    return {func_name: params}
