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
    """Extract function call parameters from user query and return as {func_name: {params}}."""
    
    # Parse prompt - may be JSON string with nested structure
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
            # Extract user content from BFCL format: {"question": [[{"role": "user", "content": "..."}]]}
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
        funcs = json.loads(functions) if isinstance(functions, str) else functions
    except (json.JSONDecodeError, TypeError):
        funcs = []
    
    if not funcs:
        return {"error": "No functions provided"}
    
    func = funcs[0]
    func_name = func.get("name", "")
    props = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters using regex
    params = {}
    
    # For mortgage_calculator, extract: loan_amount, interest_rate, loan_period
    
    # Extract loan amount - look for dollar amounts like $350,000 or 350000
    loan_amount_patterns = [
        r'\$\s*([\d,]+(?:\.\d+)?)',  # $350,000 or $350000
        r'(?:priced at|amount of|loan of|house (?:priced|worth|costing))\s*\$?\s*([\d,]+(?:\.\d+)?)',
        r'([\d,]+(?:\.\d+)?)\s*(?:dollar|USD)',
    ]
    
    loan_amount = None
    for pattern in loan_amount_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            amount_str = match.group(1).replace(',', '')
            loan_amount = float(amount_str)
            break
    
    # Extract interest rate - look for percentages like 3.5%
    interest_rate_patterns = [
        r'(?:interest rate|rate)\s*(?:of|about|around|approximately)?\s*([\d.]+)\s*%',
        r'([\d.]+)\s*%\s*(?:interest|rate)',
        r'([\d.]+)\s*percent',
    ]
    
    interest_rate = None
    for pattern in interest_rate_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            rate_percent = float(match.group(1))
            # Convert percentage to decimal (0-1 range as per schema)
            interest_rate = rate_percent / 100.0
            break
    
    # Extract loan period - look for years like "30-year" or "30 years"
    loan_period_patterns = [
        r'(\d+)\s*-?\s*year\s*(?:mortgage|loan|term|period)?',
        r'(?:period|term)\s*(?:of)?\s*(\d+)\s*years?',
        r'(\d+)\s*years?\s*(?:mortgage|loan)',
    ]
    
    loan_period = None
    for pattern in loan_period_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            loan_period = int(match.group(1))
            break
    
    # Build params dict based on what we found
    if loan_amount is not None:
        params["loan_amount"] = loan_amount
    if interest_rate is not None:
        params["interest_rate"] = interest_rate
    if loan_period is not None:
        params["loan_period"] = loan_period
    
    return {func_name: params}
