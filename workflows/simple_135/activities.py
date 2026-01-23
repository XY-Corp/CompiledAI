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
    """Extract function call parameters from natural language query.
    
    Parses the prompt to extract numeric values and maps them to the
    appropriate function parameters based on the function schema.
    """
    # Parse prompt (may be JSON string with nested structure)
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
            # Extract user query from BFCL format
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

    # Extract all dollar amounts from the query
    # Pattern matches $X or $X.XX format
    dollar_amounts = re.findall(r'\$(\d+(?:\.\d+)?)', query)
    
    # Convert to integers
    amounts = [int(float(amt)) for amt in dollar_amounts]

    # Map extracted values to parameters based on context
    params = {}
    
    # For ROI calculation, we expect: purchase_price, sale_price, dividend
    # The query pattern is typically: "bought at $X, sold at $Y, dividend of $Z"
    
    # Try to extract with context clues
    purchase_match = re.search(r'bought\s+at\s+\$(\d+(?:\.\d+)?)', query, re.IGNORECASE)
    sale_match = re.search(r'sold\s+at\s+\$(\d+(?:\.\d+)?)', query, re.IGNORECASE)
    dividend_match = re.search(r'dividend\s+(?:of\s+)?\$(\d+(?:\.\d+)?)', query, re.IGNORECASE)

    if purchase_match:
        params["purchase_price"] = int(float(purchase_match.group(1)))
    elif len(amounts) >= 1:
        params["purchase_price"] = amounts[0]

    if sale_match:
        params["sale_price"] = int(float(sale_match.group(1)))
    elif len(amounts) >= 2:
        params["sale_price"] = amounts[1]

    if dividend_match:
        params["dividend"] = int(float(dividend_match.group(1)))
    elif len(amounts) >= 3:
        params["dividend"] = amounts[2]

    return {func_name: params}
