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
    """Extract function name and parameters from user query using regex patterns."""
    
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
    
    # Get function details
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    props = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters using regex
    params = {}
    
    # Extract coupon_payment - look for dollar amounts or "coupon payment of X"
    coupon_patterns = [
        r'coupon\s+payment\s+of\s+\$?(\d+)',
        r'\$(\d+)\s+(?:annually|annual|per\s+year)',
        r'payment\s+of\s+\$?(\d+)',
        r'\$(\d+)\s+coupon',
    ]
    for pattern in coupon_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            params["coupon_payment"] = int(match.group(1))
            break
    
    # Extract period - look for "X years" or "next X years"
    period_patterns = [
        r'(?:for\s+)?(?:next\s+)?(\d+)\s+years?',
        r'(\d+)\s+year\s+(?:period|time\s+frame)',
        r'time\s+frame\s+(?:of\s+)?(\d+)',
    ]
    for pattern in period_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            params["period"] = int(match.group(1))
            break
    
    # Extract discount_rate - look for "X%" or "discount rate X%"
    rate_patterns = [
        r'discount\s+rate\s+(?:of\s+)?(\d+(?:\.\d+)?)\s*%',
        r'(\d+(?:\.\d+)?)\s*%\s*(?:discount)?',
        r'rate\s+(?:of\s+)?(\d+(?:\.\d+)?)\s*%',
    ]
    for pattern in rate_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            # Convert percentage to decimal (4% -> 0.04)
            params["discount_rate"] = float(match.group(1)) / 100.0
            break
    
    # Extract face_value if mentioned (optional parameter)
    face_patterns = [
        r'face\s+value\s+(?:of\s+)?\$?(\d+)',
        r'\$(\d+)\s+face\s+value',
        r'par\s+value\s+(?:of\s+)?\$?(\d+)',
    ]
    for pattern in face_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            params["face_value"] = int(match.group(1))
            break
    
    return {func_name: params}
