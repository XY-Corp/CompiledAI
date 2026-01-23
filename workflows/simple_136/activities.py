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
    """Extract function call parameters from natural language query using regex patterns."""
    
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
    
    if not funcs:
        return {"error": "No functions provided"}
    
    func = funcs[0]
    func_name = func.get("name", "")
    props = func.get("parameters", {}).get("properties", {})
    
    params = {}
    query_lower = query.lower()
    
    # Extract principal (dollar amount)
    # Patterns: "$10000", "$10,000", "10000 dollars", "investment of $10000"
    principal_patterns = [
        r'\$\s*([\d,]+(?:\.\d+)?)',  # $10000 or $10,000
        r'([\d,]+(?:\.\d+)?)\s*(?:dollars?|usd)',  # 10000 dollars
        r'investment\s+of\s+\$?\s*([\d,]+(?:\.\d+)?)',  # investment of $10000
        r'principal\s+(?:of\s+)?\$?\s*([\d,]+(?:\.\d+)?)',  # principal of 10000
    ]
    
    for pattern in principal_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            principal_str = match.group(1).replace(',', '')
            params["principal"] = int(float(principal_str))
            break
    
    # Extract annual rate (percentage)
    # Patterns: "5%", "5 percent", "interest rate of 5%", "annual rate of 5%"
    rate_patterns = [
        r'(?:annual\s+)?(?:interest\s+)?rate\s+of\s+([\d.]+)\s*%?',  # rate of 5%
        r'([\d.]+)\s*%\s*(?:annual|yearly|per\s+year)?',  # 5% annual
        r'([\d.]+)\s*percent',  # 5 percent
    ]
    
    for pattern in rate_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            params["annual_rate"] = float(match.group(1))
            break
    
    # Extract compounding frequency
    # Look for keywords: monthly, quarterly, annually
    if "monthly" in query_lower or "compounded monthly" in query_lower:
        params["compounding_freq"] = "monthly"
    elif "quarterly" in query_lower or "compounded quarterly" in query_lower:
        params["compounding_freq"] = "quarterly"
    elif "annually" in query_lower or "compounded annually" in query_lower or "yearly" in query_lower:
        params["compounding_freq"] = "annually"
    
    # Extract time in years
    # Patterns: "5 years", "for 5 years", "time period of 5 years"
    time_patterns = [
        r'for\s+(\d+)\s*years?',  # for 5 years
        r'(\d+)\s*years?\s*(?:period|time)?',  # 5 years
        r'time\s+(?:period\s+)?(?:of\s+)?(\d+)\s*years?',  # time period of 5 years
    ]
    
    for pattern in time_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            params["time_in_years"] = int(match.group(1))
            break
    
    return {func_name: params}
