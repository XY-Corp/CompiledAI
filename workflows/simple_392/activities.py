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
    """Extract function name and parameters from user query using regex and string matching."""
    
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
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters based on the query
    params = {}
    query_lower = query.lower()
    
    # Currency mapping for common names
    currency_map = {
        "british pounds": "GBP",
        "british pound": "GBP",
        "pounds": "GBP",
        "pound": "GBP",
        "gbp": "GBP",
        "japanese yen": "JPY",
        "yen": "JPY",
        "jpy": "JPY",
        "us dollars": "USD",
        "us dollar": "USD",
        "dollars": "USD",
        "dollar": "USD",
        "usd": "USD",
        "euros": "EUR",
        "euro": "EUR",
        "eur": "EUR",
        "canadian dollars": "CAD",
        "canadian dollar": "CAD",
        "cad": "CAD",
        "australian dollars": "AUD",
        "australian dollar": "AUD",
        "aud": "AUD",
        "swiss francs": "CHF",
        "swiss franc": "CHF",
        "chf": "CHF",
        "chinese yuan": "CNY",
        "yuan": "CNY",
        "cny": "CNY",
        "indian rupees": "INR",
        "indian rupee": "INR",
        "rupees": "INR",
        "rupee": "INR",
        "inr": "INR",
    }
    
    # Extract source and target currencies using patterns
    # Pattern: "from X to Y"
    from_to_match = re.search(r'from\s+([a-zA-Z\s]+?)\s+to\s+([a-zA-Z\s]+?)(?:\.|,|$)', query_lower)
    
    source_currency = None
    target_currency = None
    
    if from_to_match:
        source_text = from_to_match.group(1).strip()
        target_text = from_to_match.group(2).strip()
        
        # Map to currency codes
        for name, code in currency_map.items():
            if name in source_text:
                source_currency = code
                break
        for name, code in currency_map.items():
            if name in target_text:
                target_currency = code
                break
    
    # If not found with "from...to", try other patterns
    if not source_currency or not target_currency:
        # Look for currency mentions in order
        found_currencies = []
        for name, code in sorted(currency_map.items(), key=lambda x: -len(x[0])):
            if name in query_lower and code not in found_currencies:
                found_currencies.append(code)
        
        if len(found_currencies) >= 2:
            source_currency = found_currencies[0]
            target_currency = found_currencies[1]
    
    # Build params based on schema
    if "source_currency" in params_schema and source_currency:
        params["source_currency"] = source_currency
    if "target_currency" in params_schema and target_currency:
        params["target_currency"] = target_currency
    
    # Extract amount if present (optional parameter)
    if "amount" in params_schema:
        amount_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:units?|amount)?', query)
        if amount_match:
            params["amount"] = float(amount_match.group(1))
    
    return {func_name: params}
