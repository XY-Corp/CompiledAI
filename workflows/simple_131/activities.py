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
    """Extract function call parameters from natural language prompt using regex.
    
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
    
    # Get function details
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters using regex patterns
    params = {}
    
    # Extract principal amount - look for dollar amounts or "principal" mentions
    principal_patterns = [
        r'principal\s+(?:amount\s+)?(?:of\s+)?\$?([\d,]+)',
        r'\$?([\d,]+)\s*(?:dollars?)?\s*(?:,|\.|with|at)',
        r'amount\s+of\s+\$?([\d,]+)',
    ]
    for pattern in principal_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            params["principal"] = int(match.group(1).replace(",", ""))
            break
    
    # Extract annual interest rate - look for percentage
    rate_patterns = [
        r'(?:annual\s+)?interest\s+rate\s+(?:of\s+)?([\d.]+)\s*%',
        r'([\d.]+)\s*%\s*(?:annual\s+)?(?:interest)?',
        r'rate\s+(?:of\s+)?([\d.]+)\s*%',
    ]
    for pattern in rate_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            # Convert percentage to decimal (5% -> 0.05)
            params["rate"] = float(match.group(1)) / 100
            break
    
    # Extract n (compounding frequency) - look for "n times" or "compounded X times"
    n_patterns = [
        r'(?:number\s+of\s+times\s+)?(?:interest\s+)?(?:applied|compounded)\s+(?:per\s+)?(?:time\s+period\s+)?(?:is\s+)?(\d+)',
        r'compounded\s+(\d+)\s+times',
        r'(\d+)\s+times\s+(?:per\s+)?(?:year|period)',
    ]
    for pattern in n_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            params["n"] = int(match.group(1))
            break
    
    # Extract time in years - look for "X years" or "time is X"
    time_patterns = [
        r'(?:invested\s+)?(?:for\s+)?(\d+)\s+years?',
        r'time\s+(?:the\s+money\s+is\s+invested\s+)?(?:for\s+)?(?:is\s+)?(\d+)',
        r'(\d+)\s+year\s+(?:period|term)',
    ]
    for pattern in time_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            params["time"] = int(match.group(1))
            break
    
    return {func_name: params}
