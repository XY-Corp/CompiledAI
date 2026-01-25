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
    """Extract function call parameters from natural language query.
    
    Returns a dict with function name as key and parameters as nested object.
    Uses regex extraction - no LLM calls needed.
    """
    # Parse prompt (may be JSON string with nested structure)
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
        else:
            data = prompt
        
        # Extract user query from BFCL format
        if "question" in data and isinstance(data["question"], list):
            if len(data["question"]) > 0 and isinstance(data["question"][0], list):
                query = data["question"][0][0].get("content", str(prompt))
            else:
                query = str(prompt)
        else:
            query = str(prompt)
    except (json.JSONDecodeError, TypeError, KeyError):
        query = str(prompt)
    
    # Parse functions (may be JSON string)
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
    
    # Extract parameters from query using regex
    params = {}
    
    # Extract principal (dollar amount)
    # Patterns: "$10000", "$10,000", "10000 dollars", "investment of $10000"
    principal_patterns = [
        r'\$\s*([\d,]+(?:\.\d+)?)',  # $10000 or $10,000
        r'([\d,]+(?:\.\d+)?)\s*(?:dollars?|USD)',  # 10000 dollars
        r'investment\s+of\s+\$?\s*([\d,]+(?:\.\d+)?)',  # investment of 10000
        r'principal\s+(?:of\s+)?\$?\s*([\d,]+(?:\.\d+)?)',  # principal of 10000
    ]
    for pattern in principal_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            params["principal"] = int(match.group(1).replace(",", "").split(".")[0])
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
    # Look for: "monthly", "quarterly", "annually", "compounded monthly"
    freq_patterns = [
        r'compounded\s+(monthly|quarterly|annually)',
        r'(monthly|quarterly|annually)\s+compound',
        r'\b(monthly|quarterly|annually)\b',
    ]
    for pattern in freq_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            params["compounding_freq"] = match.group(1).lower()
            break
    
    # Extract time in years
    # Patterns: "5 years", "for 5 years", "time period of 5 years"
    time_patterns = [
        r'(?:for\s+)?([\d.]+)\s*years?',  # 5 years, for 5 years
        r'time\s+(?:period\s+)?(?:of\s+)?([\d.]+)\s*years?',  # time period of 5 years
        r'([\d.]+)\s*(?:year|yr)s?\s+(?:period|term)',  # 5 year period
    ]
    for pattern in time_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            params["time_in_years"] = int(float(match.group(1)))
            break
    
    return {func_name: params}
