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

    # Get target function details
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})

    # Extract all numbers from the query
    # Pattern matches integers and decimals, including those with $ or % symbols
    numbers = re.findall(r'\$?([\d,]+(?:\.\d+)?)\s*%?', query)
    # Clean numbers - remove commas
    cleaned_numbers = [n.replace(',', '') for n in numbers if n]

    # Build parameters based on schema
    params = {}
    
    # For calculate_future_value, we expect:
    # - present_value (float): the dollar amount invested
    # - interest_rate (float): the rate (0-1)
    # - periods (integer): number of years
    
    # Extract present_value - look for dollar amounts
    pv_patterns = [
        r'\$\s*([\d,]+(?:\.\d+)?)',  # $5000 or $ 5000
        r'([\d,]+(?:\.\d+)?)\s*(?:dollars?|USD)',  # 5000 dollars
        r'(?:put|invest(?:ed)?|deposit(?:ed)?)\s*\$?\s*([\d,]+(?:\.\d+)?)',  # put $5000
    ]
    
    present_value = None
    for pattern in pv_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            present_value = float(match.group(1).replace(',', ''))
            break
    
    # Extract interest_rate - look for percentage
    rate_patterns = [
        r'([\d.]+)\s*%\s*(?:annual|yearly|interest|rate)?',  # 5% annual
        r'(?:rate|interest)\s*(?:of|is)?\s*([\d.]+)\s*%?',  # rate of 5%
    ]
    
    interest_rate = None
    for pattern in rate_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            rate_value = float(match.group(1))
            # Convert percentage to decimal if > 1
            interest_rate = rate_value / 100 if rate_value > 1 else rate_value
            break
    
    # Extract periods - look for years
    period_patterns = [
        r'(\d+)\s*years?',  # 10 years
        r'for\s*(\d+)\s*(?:years?|periods?)',  # for 10 years
        r'(\d+)\s*(?:year|annual)\s*periods?',  # 10 year periods
    ]
    
    periods = None
    for pattern in period_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            periods = int(match.group(1))
            break

    # Build result based on what we found
    if "present_value" in params_schema and present_value is not None:
        params["present_value"] = present_value
    
    if "interest_rate" in params_schema and interest_rate is not None:
        params["interest_rate"] = interest_rate
    
    if "periods" in params_schema and periods is not None:
        params["periods"] = periods

    return {func_name: params}
