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
    
    params = {}
    query_lower = query.lower()
    
    # Extract stock_name - look for stock symbols (uppercase letters, typically 1-5 chars)
    # Common patterns: "AAPL", "of AAPL", "Apple's stock" -> AAPL
    stock_symbols = re.findall(r'\b([A-Z]{1,5})\b', query)
    # Filter out common words that might be uppercase
    common_words = {'I', 'A', 'THE', 'AND', 'OR', 'FOR', 'TO', 'IN', 'OF', 'CAN', 'YOU'}
    stock_symbols = [s for s in stock_symbols if s not in common_words]
    
    if stock_symbols:
        params["stock_name"] = stock_symbols[0]
    
    # Extract interval - look for interval keywords
    interval_map = {
        "5m": ["5m", "5 minute", "5-minute", "five minute"],
        "15m": ["15m", "15 minute", "15-minute", "fifteen minute"],
        "30m": ["30m", "30 minute", "30-minute", "thirty minute"],
        "1h": ["1h", "1 hour", "1-hour", "one hour", "hourly"],
        "1d": ["1d", "1 day", "1-day", "one day", "daily"],
        "1wk": ["1wk", "1 week", "1-week", "one week", "weekly"],
        "1mo": ["1mo", "1 month", "1-month", "one month", "monthly"],
        "3mo": ["3mo", "3 month", "3-month", "three month", "quarterly"]
    }
    
    for interval_code, patterns in interval_map.items():
        for pattern in patterns:
            if pattern in query_lower:
                params["interval"] = interval_code
                break
        if "interval" in params:
            break
    
    # Extract diffandsplits - look for splits/dividends mentions
    splits_keywords = ["split", "splits", "dividend", "dividends", "diffandsplits"]
    has_splits_mention = any(kw in query_lower for kw in splits_keywords)
    
    if has_splits_mention:
        params["diffandsplits"] = "true"
    
    return {func_name: params}
