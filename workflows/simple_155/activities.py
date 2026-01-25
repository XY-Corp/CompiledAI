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
    
    # Parse prompt (may be JSON string with nested structure)
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
    
    # Parse functions (may be JSON string)
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
    
    # Extract values using regex patterns
    params = {}
    
    # Extract monetary amounts (for initial_investment)
    # Patterns: $1000, $1,000, 1000 dollars, etc.
    money_patterns = [
        r'\$\s*([\d,]+(?:\.\d+)?)',  # $1000 or $1,000
        r'([\d,]+(?:\.\d+)?)\s*(?:dollars?|USD)',  # 1000 dollars
        r'investment\s+of\s+\$?([\d,]+(?:\.\d+)?)',  # investment of $1000
    ]
    
    money_value = None
    for pattern in money_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            money_value = float(match.group(1).replace(',', ''))
            break
    
    # Extract percentage (for interest_rate)
    # Patterns: 5%, 5 percent, 0.05 rate
    rate_patterns = [
        r'(\d+(?:\.\d+)?)\s*%',  # 5%
        r'(\d+(?:\.\d+)?)\s*percent',  # 5 percent
        r'rate\s+of\s+(\d+(?:\.\d+)?)\s*%?',  # rate of 5%
        r'interest\s+rate\s+of\s+(\d+(?:\.\d+)?)\s*%?',  # interest rate of 5%
    ]
    
    rate_value = None
    for pattern in rate_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            rate_value = float(match.group(1))
            # Convert percentage to decimal if > 1
            if rate_value > 1:
                rate_value = rate_value / 100
            break
    
    # Extract duration (for duration in years)
    # Patterns: 2 years, over 2 years, for 2 years
    duration_patterns = [
        r'(\d+)\s*years?',  # 2 years
        r'over\s+(\d+)\s*years?',  # over 2 years
        r'for\s+(\d+)\s*years?',  # for 2 years
        r'duration\s+of\s+(\d+)',  # duration of 2
    ]
    
    duration_value = None
    for pattern in duration_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            duration_value = int(match.group(1))
            break
    
    # Extract compounding frequency (optional)
    # Patterns: compounded monthly, compounded 12 times
    compound_patterns = [
        r'compounded\s+(\d+)\s*times',  # compounded 12 times
        r'compounded\s+monthly',  # compounded monthly -> 12
        r'compounded\s+quarterly',  # compounded quarterly -> 4
        r'compounded\s+daily',  # compounded daily -> 365
        r'compounded\s+annually',  # compounded annually -> 1
    ]
    
    compound_value = None
    for pattern in compound_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            if 'monthly' in pattern:
                compound_value = 12
            elif 'quarterly' in pattern:
                compound_value = 4
            elif 'daily' in pattern:
                compound_value = 365
            elif 'annually' in pattern:
                compound_value = 1
            else:
                compound_value = int(match.group(1))
            break
    
    # Map extracted values to parameter names based on schema
    for param_name, param_info in props.items():
        param_type = param_info.get("type", "string")
        
        if param_name == "initial_investment" and money_value is not None:
            params[param_name] = int(money_value) if param_type == "integer" else money_value
        elif param_name == "interest_rate" and rate_value is not None:
            params[param_name] = rate_value
        elif param_name == "duration" and duration_value is not None:
            params[param_name] = duration_value
        elif param_name == "compounded" and compound_value is not None:
            params[param_name] = compound_value
    
    return {func_name: params}
