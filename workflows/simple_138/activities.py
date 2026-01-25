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
    
    # Get function schema
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    props = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters from query using regex
    params = {}
    
    # Extract stock ticker - look for patterns like 'stock X', 'stock "X"', 'stock 'X''
    stock_patterns = [
        r"stock\s+['\"]?([A-Za-z]+)['\"]?",
        r"ticker\s+['\"]?([A-Za-z]+)['\"]?",
        r"symbol\s+['\"]?([A-Za-z]+)['\"]?",
    ]
    for pattern in stock_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            params["stock"] = match.group(1).upper()
            break
    
    # Extract invested amount - look for dollar amounts
    amount_patterns = [
        r"\$\s*([\d,]+(?:\.\d+)?)",
        r"invest\s+\$?([\d,]+(?:\.\d+)?)",
        r"([\d,]+(?:\.\d+)?)\s*(?:dollars|USD)",
    ]
    for pattern in amount_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            amount_str = match.group(1).replace(",", "")
            params["invested_amount"] = int(float(amount_str))
            break
    
    # Extract expected annual return - look for percentage
    return_patterns = [
        r"(\d+(?:\.\d+)?)\s*%\s*(?:annual|yearly|return|interest)?",
        r"return\s+(?:of\s+)?(\d+(?:\.\d+)?)\s*%",
        r"(\d+(?:\.\d+)?)\s*percent",
    ]
    for pattern in return_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            # Convert percentage to decimal (5% -> 0.05)
            params["expected_annual_return"] = float(match.group(1)) / 100.0
            break
    
    # Extract years - look for number of years
    years_patterns = [
        r"(\d+)\s*years?",
        r"for\s+(\d+)\s*(?:years?|yrs?)",
        r"(\d+)\s*(?:year|yr)\s*(?:period|term)?",
    ]
    for pattern in years_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            params["years"] = int(match.group(1))
            break
    
    return {func_name: params}
