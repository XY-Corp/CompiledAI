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
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters using regex
    params = {}
    
    # Extract dollar amounts (investment_amount)
    dollar_match = re.search(r'\$(\d+(?:,\d{3})*(?:\.\d+)?)', query)
    if dollar_match:
        amount_str = dollar_match.group(1).replace(',', '')
        params["investment_amount"] = int(float(amount_str))
    
    # Extract percentage (annual_growth_rate)
    percent_match = re.search(r'(\d+(?:\.\d+)?)\s*%', query)
    if percent_match:
        # Convert percentage to decimal (6% -> 0.06)
        params["annual_growth_rate"] = float(percent_match.group(1)) / 100
    
    # Extract holding period (years)
    years_match = re.search(r'(\d+)\s*years?', query, re.IGNORECASE)
    if years_match:
        params["holding_period"] = int(years_match.group(1))
    
    # Check for dividends mention (optional parameter)
    if re.search(r'\bdividends?\b', query, re.IGNORECASE):
        params["dividends"] = True
    
    return {func_name: params}
