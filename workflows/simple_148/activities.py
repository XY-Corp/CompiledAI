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
    initial_patterns = [
        r'initial\s+investment\s+of\s+\$?([\d,]+)',
        r'\$?([\d,]+)\s+(?:initial|invested)',
        r'invest(?:ment|ing)?\s+(?:of\s+)?\$?([\d,]+)',
    ]
    for pattern in initial_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            params["initial_investment"] = int(match.group(1).replace(",", ""))
            break
    
    # Extract rate_of_return - look for percentage values
    rate_patterns = [
        r'(?:annual\s+)?rate\s+(?:of\s+return\s+)?(?:of\s+)?([\d.]+)%',
        r'([\d.]+)%\s+(?:annual\s+)?(?:rate|return)',
        r'return\s+(?:of\s+)?([\d.]+)%',
    ]
    for pattern in rate_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            # Convert percentage to decimal (8% -> 0.08)
            params["rate_of_return"] = float(match.group(1)) / 100
            break
    
    # Extract years - look for time frame
    years_patterns = [
        r'(\d+)\s+years?',
        r'time\s+frame\s+of\s+(\d+)',
        r'(\d+)\s+year\s+(?:time\s+)?(?:frame|period)',
    ]
    for pattern in years_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            params["years"] = int(match.group(1))
            break
    
    # Extract contribution (optional) - look for additional/regular contributions
    contribution_patterns = [
        r'contribution[s]?\s+(?:of\s+)?\$?([\d,]+)',
        r'additional\s+(?:regular\s+)?(?:contribution[s]?\s+)?(?:of\s+)?\$?([\d,]+)',
        r'\$?([\d,]+)\s+(?:additional|regular)\s+contribution',
    ]
    for pattern in contribution_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            params["contribution"] = int(match.group(1).replace(",", ""))
            break
    
    return {func_name: params}
