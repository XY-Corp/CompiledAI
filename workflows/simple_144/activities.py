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
    """Extract function call parameters from user query and return as {func_name: {params}}."""
    
    # Parse prompt (may be JSON string with nested structure)
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
            # Handle BFCL format: {"question": [[{"role": "user", "content": "..."}]], "function": [...]}
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
    
    if not funcs:
        return {"error": "No functions provided"}
    
    func = funcs[0]
    func_name = func.get("name", "")
    props = func.get("parameters", {}).get("properties", {})
    
    params = {}
    query_lower = query.lower()
    
    # Extract indexes (array of strings)
    if "indexes" in props:
        indexes = []
        # Known index patterns to look for
        known_indexes = ["S&P 500", "Dow Jones", "NASDAQ", "FTSE 100", "DAX"]
        for idx in known_indexes:
            if idx.lower() in query_lower:
                indexes.append(idx)
        if indexes:
            params["indexes"] = indexes
    
    # Extract days (integer)
    if "days" in props:
        # Look for patterns like "past 5 days", "5 days", "last 5 days"
        days_patterns = [
            r'(?:past|last)\s+(\d+)\s+days?',
            r'(\d+)\s+days?\s+(?:ago|back|period)',
            r'over\s+(?:the\s+)?(?:past|last)\s+(\d+)\s+days?',
            r'(\d+)\s+days?'
        ]
        for pattern in days_patterns:
            match = re.search(pattern, query_lower)
            if match:
                params["days"] = int(match.group(1))
                break
    
    # Extract detailed (boolean) - only if explicitly mentioned
    if "detailed" in props:
        if any(word in query_lower for word in ["detailed", "detail", "high", "low", "opening", "closing"]):
            params["detailed"] = True
        # Don't include if not mentioned (optional param with default)
    
    return {func_name: params}
