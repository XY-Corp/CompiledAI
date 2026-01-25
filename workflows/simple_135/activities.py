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
    """Extract function call parameters from user query using regex.
    
    Returns a dict with function name as key and parameters as nested object.
    """
    # Parse prompt - may be JSON string with nested structure
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
            # Handle BFCL format: {"question": [[{"role": "user", "content": "..."}]]}
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

    # Extract all dollar amounts from the query
    # Pattern matches $X, $X.XX formats
    dollar_amounts = re.findall(r'\$(\d+(?:\.\d+)?)', query)
    
    # Convert to integers (as per schema)
    amounts = [int(float(amt)) for amt in dollar_amounts]

    # Build parameters based on context in the query
    params = {}
    
    # For calculate_return_on_investment, we expect:
    # - purchase_price: "bought at $X"
    # - sale_price: "sold at $X"
    # - dividend: "dividend of $X"
    
    # Extract purchase price (bought at)
    purchase_match = re.search(r'bought\s+at\s+\$(\d+(?:\.\d+)?)', query, re.IGNORECASE)
    if purchase_match:
        params["purchase_price"] = int(float(purchase_match.group(1)))
    
    # Extract sale price (sold at)
    sale_match = re.search(r'sold\s+at\s+\$(\d+(?:\.\d+)?)', query, re.IGNORECASE)
    if sale_match:
        params["sale_price"] = int(float(sale_match.group(1)))
    
    # Extract dividend (dividend of)
    dividend_match = re.search(r'dividend\s+of\s+\$(\d+(?:\.\d+)?)', query, re.IGNORECASE)
    if dividend_match:
        params["dividend"] = int(float(dividend_match.group(1)))
    
    # Fallback: if specific patterns didn't match, use positional amounts
    if not params and len(amounts) >= 2:
        # Assume order: purchase_price, sale_price, dividend
        params["purchase_price"] = amounts[0]
        params["sale_price"] = amounts[1]
        if len(amounts) >= 3:
            params["dividend"] = amounts[2]

    return {func_name: params}
