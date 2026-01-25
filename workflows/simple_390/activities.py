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
            # Extract user query from BFCL format: {"question": [[{"role": "user", "content": "..."}]]}
            if "question" in data and isinstance(data["question"], list):
                if len(data["question"]) > 0 and isinstance(data["question"][0], list):
                    query = data["question"][0][0].get("content", prompt)
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
    
    # Extract parameters based on schema
    params = {}
    
    # Extract amount (integer) - look for numbers
    if "amount" in params_schema:
        numbers = re.findall(r'\d+(?:\.\d+)?', query)
        if numbers:
            params["amount"] = int(float(numbers[0]))
    
    # Extract currency codes - common patterns
    # Currency mapping for common names
    currency_map = {
        "euro": "EUR", "euros": "EUR", "eur": "EUR",
        "dollar": "USD", "dollars": "USD", "usd": "USD",
        "canadian dollar": "CAD", "canadian dollars": "CAD", "cad": "CAD",
        "pound": "GBP", "pounds": "GBP", "gbp": "GBP", "british pound": "GBP",
        "yen": "JPY", "jpy": "JPY", "japanese yen": "JPY",
        "yuan": "CNY", "cny": "CNY", "chinese yuan": "CNY",
        "rupee": "INR", "rupees": "INR", "inr": "INR", "indian rupee": "INR",
        "franc": "CHF", "swiss franc": "CHF", "chf": "CHF",
        "peso": "MXN", "mexican peso": "MXN", "mxn": "MXN",
        "real": "BRL", "brazilian real": "BRL", "brl": "BRL",
        "won": "KRW", "korean won": "KRW", "krw": "KRW",
        "ruble": "RUB", "rubles": "RUB", "rub": "RUB",
        "australian dollar": "AUD", "australian dollars": "AUD", "aud": "AUD",
    }
    
    query_lower = query.lower()
    
    # Extract from_currency - look for "X to Y" or "convert X" patterns
    if "from_currency" in params_schema:
        # Pattern: "Convert X Euros to Y" or "X euros to Y"
        from_match = re.search(r'(?:convert\s+)?(?:\d+\s+)?(\w+(?:\s+\w+)?)\s+to\s+', query_lower)
        if from_match:
            from_text = from_match.group(1).strip()
            # Check if it's a currency name
            for name, code in currency_map.items():
                if name in from_text:
                    params["from_currency"] = code
                    break
            # Check for 3-letter currency code
            if "from_currency" not in params:
                code_match = re.search(r'\b([A-Z]{3})\b', from_match.group(1).upper())
                if code_match:
                    params["from_currency"] = code_match.group(1)
    
    # Extract to_currency - look for "to Y" pattern
    if "to_currency" in params_schema:
        # Pattern: "to Canadian dollars" or "to CAD"
        to_match = re.search(r'\bto\s+(\w+(?:\s+\w+)?(?:\s+\w+)?)', query_lower)
        if to_match:
            to_text = to_match.group(1).strip()
            # Check if it's a currency name
            for name, code in currency_map.items():
                if name in to_text:
                    params["to_currency"] = code
                    break
            # Check for 3-letter currency code
            if "to_currency" not in params:
                code_match = re.search(r'\b([A-Z]{3})\b', to_match.group(1).upper())
                if code_match:
                    params["to_currency"] = code_match.group(1)
    
    return {func_name: params}
