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
    
    Parses the user query to extract parameter values and returns them
    in the format {"function_name": {"param1": val1, ...}}.
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
    except (json.JSONDecodeError, TypeError):
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
    
    # Extract parameters using regex
    params = {}
    
    # Extract initial_investment - look for dollar amounts or "initial investment of X"
    initial_match = re.search(r'initial\s+investment\s+of\s+\$?([\d,]+)', query, re.IGNORECASE)
    if not initial_match:
        initial_match = re.search(r'\$?([\d,]+)\s*(?:initial|investment)', query, re.IGNORECASE)
    if not initial_match:
        # Look for dollar amounts in general
        dollar_matches = re.findall(r'\$([\d,]+)', query)
        if dollar_matches:
            initial_match = type('Match', (), {'group': lambda self, n: dollar_matches[0]})()
    
    if initial_match:
        params["initial_investment"] = int(initial_match.group(1).replace(',', ''))
    
    # Extract rate_of_return - look for percentage or "rate of X%"
    rate_match = re.search(r'(?:rate\s+of\s+(?:return\s+)?(?:of\s+)?|annual\s+rate\s+of\s+(?:return\s+)?(?:of\s+)?|return\s+of\s+)([\d.]+)\s*%?', query, re.IGNORECASE)
    if not rate_match:
        rate_match = re.search(r'([\d.]+)\s*%\s*(?:rate|return|annual)', query, re.IGNORECASE)
    if not rate_match:
        # Look for any percentage
        rate_match = re.search(r'([\d.]+)\s*%', query)
    
    if rate_match:
        rate_value = float(rate_match.group(1))
        # Convert percentage to decimal if it's greater than 1 (e.g., 8% -> 0.08)
        if rate_value > 1:
            rate_value = rate_value / 100
        params["rate_of_return"] = rate_value
    
    # Extract years - look for "X years" or "time frame of X"
    years_match = re.search(r'(?:time\s+frame\s+of\s+|for\s+|over\s+)([\d]+)\s*years?', query, re.IGNORECASE)
    if not years_match:
        years_match = re.search(r'([\d]+)\s*years?', query, re.IGNORECASE)
    
    if years_match:
        params["years"] = int(years_match.group(1))
    
    # Extract contribution (optional) - look for "contribution of X" or "regular contribution"
    contrib_match = re.search(r'(?:contribution|contributions)\s+(?:of\s+)?\$?([\d,]+)', query, re.IGNORECASE)
    if not contrib_match:
        contrib_match = re.search(r'(?:additional|regular)\s+\$?([\d,]+)', query, re.IGNORECASE)
    
    if contrib_match:
        params["contribution"] = int(contrib_match.group(1).replace(',', ''))
    
    return {func_name: params}
