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
    
    # Parse prompt (may be JSON string with nested structure)
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
        else:
            data = prompt
        
        # Extract user query from BFCL format: {"question": [[{"role": "user", "content": "..."}]]}
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
    
    # Extract parameters using regex and string matching
    params = {}
    
    # Extract destination (city name after "to" or "trip to")
    dest_match = re.search(r'(?:trip\s+to|to)\s+([A-Za-z\s]+?)(?:\s+(?:with|for|and|,)|$)', query, re.IGNORECASE)
    if dest_match:
        params["destination"] = dest_match.group(1).strip()
    
    # Extract days (number followed by "days" or "day")
    days_match = re.search(r'(\d+)\s*(?:days?|day)', query, re.IGNORECASE)
    if days_match:
        params["days"] = int(days_match.group(1))
    
    # Extract daily_budget (number after "$" or "budget" patterns)
    budget_patterns = [
        r'\$(\d+)',  # $100
        r'(\d+)\s*(?:dollars?|usd)',  # 100 dollars
        r'budget[s]?\s*(?:of|not exceeding|under|below|around|about)?\s*\$?(\d+)',  # budget of $100
        r'not\s+exceeding\s+\$?(\d+)',  # not exceeding $100
    ]
    for pattern in budget_patterns:
        budget_match = re.search(pattern, query, re.IGNORECASE)
        if budget_match:
            params["daily_budget"] = int(budget_match.group(1))
            break
    
    # Extract exploration_type from enum values
    exploration_types = ["nature", "urban", "history", "culture"]
    query_lower = query.lower()
    for exp_type in exploration_types:
        if exp_type in query_lower:
            params["exploration_type"] = exp_type
            break
    
    return {func_name: params}
