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
    """Extract function call parameters from user query using regex and string matching."""
    
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
    
    # Extract parameters from query using regex
    params = {}
    
    # Extract stock ticker - look for 'stock' followed by quote or ticker pattern
    stock_patterns = [
        r"stock\s+['\"]?([A-Za-z]+)['\"]?",  # stock 'X' or stock X
        r"in\s+stock\s+['\"]?([A-Za-z]+)['\"]?",  # in stock 'X'
        r"ticker\s+['\"]?([A-Za-z]+)['\"]?",  # ticker 'X'
    ]
    for pattern in stock_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            params["stock"] = match.group(1)
            break
    
    # Extract invested amount - look for dollar amounts
    amount_patterns = [
        r"\$\s*([\d,]+(?:\.\d+)?)",  # $5000 or $5,000
        r"invest\s+\$?([\d,]+(?:\.\d+)?)",  # invest 5000
        r"([\d,]+(?:\.\d+)?)\s*(?:dollars|USD)",  # 5000 dollars
    ]
    for pattern in amount_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            amount_str = match.group(1).replace(",", "")
            params["invested_amount"] = int(float(amount_str))
            break
    
    # Extract expected annual return - look for percentage
    return_patterns = [
        r"(?:annual\s+)?return\s+(?:of\s+)?(\d+(?:\.\d+)?)\s*%",  # return of 5%
        r"(\d+(?:\.\d+)?)\s*%\s*(?:annual\s+)?return",  # 5% return
        r"(\d+(?:\.\d+)?)\s*%\s*(?:for|over)",  # 5% for
        r"(\d+(?:\.\d+)?)\s*(?:percent|%)",  # 5 percent or 5%
    ]
    for pattern in return_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            # Convert percentage to decimal (5% -> 0.05)
            params["expected_annual_return"] = float(match.group(1)) / 100.0
            break
    
    # Extract years - look for number followed by years
    years_patterns = [
        r"(?:for|over)\s+(\d+)\s*years?",  # for 7 years
        r"(\d+)\s*years?\s+(?:period|term|investment)",  # 7 years period
        r"(\d+)\s*-?\s*year",  # 7-year or 7 year
    ]
    for pattern in years_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            params["years"] = int(match.group(1))
            break
    
    return {func_name: params}
