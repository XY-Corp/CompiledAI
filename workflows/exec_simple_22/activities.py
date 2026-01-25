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
    
    # Parse prompt - may be JSON string with nested structure
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
            # Extract user query from BFCL format: {"question": [[{"role": "user", "content": "..."}]]}
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
    
    # Get function schema
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    props = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters based on the query content
    params = {}
    
    # Extract amount - look for numbers with optional comma separators
    amount_patterns = [
        r'(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*(?:euros?|EUR)',  # 5,000 Euros
        r'convert\s+(\d{1,3}(?:,\d{3})*(?:\.\d+)?)',  # convert 5000
        r'(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s+(?:from|in)',  # 5000 from/in
    ]
    
    amount = None
    for pattern in amount_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            amount_str = match.group(1).replace(',', '')
            amount = float(amount_str)
            break
    
    # Fallback: find any number that looks like an amount
    if amount is None:
        numbers = re.findall(r'\d{1,3}(?:,\d{3})*(?:\.\d+)?', query)
        if numbers:
            amount = float(numbers[0].replace(',', ''))
    
    # Extract currencies
    # Common currency mappings
    currency_map = {
        'euro': 'EUR', 'euros': 'EUR', 'eur': 'EUR', '€': 'EUR',
        'dollar': 'USD', 'dollars': 'USD', 'usd': 'USD', '$': 'USD',
        'yen': 'JPY', 'japanese yen': 'JPY', 'jpy': 'JPY', '¥': 'JPY',
        'pound': 'GBP', 'pounds': 'GBP', 'gbp': 'GBP', '£': 'GBP',
        'yuan': 'CNY', 'chinese yuan': 'CNY', 'cny': 'CNY', 'rmb': 'CNY',
    }
    
    query_lower = query.lower()
    
    # Detect from_currency (source)
    from_currency = None
    # Pattern: "convert X Euros" or "X Euros into"
    from_patterns = [
        r'convert\s+[\d,]+\s+(\w+)',  # convert 5000 Euros
        r'([\d,]+)\s+(\w+)\s+(?:into|to|in)',  # 5000 Euros into
    ]
    
    for pattern in from_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            # Get the currency word (last group)
            currency_word = match.group(match.lastindex).lower()
            if currency_word in currency_map:
                from_currency = currency_map[currency_word]
                break
    
    # Detect to_currency (target)
    to_currency = None
    # Pattern: "into Japanese Yen" or "to JPY"
    to_patterns = [
        r'(?:into|to|in)\s+(\w+\s+\w+)',  # into Japanese Yen
        r'(?:into|to|in)\s+(\w+)',  # into Yen
    ]
    
    for pattern in to_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            currency_phrase = match.group(1).lower()
            # Check multi-word first
            if currency_phrase in currency_map:
                to_currency = currency_map[currency_phrase]
                break
            # Check single word
            words = currency_phrase.split()
            for word in words:
                if word in currency_map:
                    to_currency = currency_map[word]
                    break
            if to_currency:
                break
    
    # Build params based on schema
    if "amount" in props and amount is not None:
        params["amount"] = amount
    if "from_currency" in props and from_currency:
        params["from_currency"] = from_currency
    if "to_currency" in props and to_currency:
        params["to_currency"] = to_currency
    
    return {func_name: params}
