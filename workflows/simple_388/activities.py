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
    
    # Parse prompt - may be JSON string with nested structure
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
    
    # Extract parameters based on the query
    params = {}
    query_lower = query.lower()
    
    # Extract amount (number)
    numbers = re.findall(r'\d+(?:\.\d+)?', query)
    if numbers:
        # For currency conversion, the amount is typically the number mentioned
        params["amount"] = int(float(numbers[0]))
    
    # Extract currencies
    # Common currency patterns
    currency_map = {
        "us dollar": "USD", "us dollars": "USD", "usd": "USD", "american dollar": "USD",
        "canadian dollar": "CAD", "canadian dollars": "CAD", "cad": "CAD",
        "euro": "EUR", "euros": "EUR", "eur": "EUR",
        "british pound": "GBP", "pounds": "GBP", "gbp": "GBP", "pound sterling": "GBP",
        "japanese yen": "JPY", "yen": "JPY", "jpy": "JPY",
        "chinese yuan": "CNY", "yuan": "CNY", "cny": "CNY", "rmb": "CNY",
        "indian rupee": "INR", "rupees": "INR", "inr": "INR",
        "australian dollar": "AUD", "australian dollars": "AUD", "aud": "AUD",
        "mexican peso": "MXN", "pesos": "MXN", "mxn": "MXN",
    }
    
    # Detect base currency (what we're converting FROM)
    # Pattern: "X [currency]" or "for X [currency]"
    base_currency = None
    target_currency = None
    
    # Look for "X US dollars" pattern (base currency)
    for currency_text, code in currency_map.items():
        # Pattern: number followed by currency (base)
        pattern = rf'\d+\s*{re.escape(currency_text)}'
        if re.search(pattern, query_lower):
            base_currency = code
            break
    
    # Look for target currency - "how many [currency]" or "convert to [currency]" or "get [currency]"
    target_patterns = [
        r'how many\s+(\w+(?:\s+\w+)?)',
        r'convert to\s+(\w+(?:\s+\w+)?)',
        r'get\s+(\w+(?:\s+\w+)?)',
        r'into\s+(\w+(?:\s+\w+)?)',
    ]
    
    for pattern in target_patterns:
        match = re.search(pattern, query_lower)
        if match:
            potential_currency = match.group(1).strip()
            for currency_text, code in currency_map.items():
                if currency_text in potential_currency or potential_currency in currency_text:
                    target_currency = code
                    break
            if target_currency:
                break
    
    # Assign to params
    if base_currency:
        params["base_currency"] = base_currency
    if target_currency:
        params["target_currency"] = target_currency
    
    return {func_name: params}
