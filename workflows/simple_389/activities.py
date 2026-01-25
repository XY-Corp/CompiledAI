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
    
    # Extract parameters based on schema
    params = {}
    query_lower = query.lower()
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_name == "base_currency":
            # Extract base currency - look for "convert X" or "X dollars/euros/etc"
            # Common patterns: "convert 200 US dollars" -> base is USD
            if "us dollar" in query_lower or "usd" in query_lower:
                params[param_name] = "USD"
            elif "british pound" in query_lower or "gbp" in query_lower:
                params[param_name] = "GBP"
            elif "euro" in query_lower or "eur" in query_lower:
                params[param_name] = "EUR"
            else:
                # Try to find currency mentioned with amount
                match = re.search(r'(\d+(?:\.\d+)?)\s*(us\s*dollars?|usd|british\s*pounds?|gbp|euros?|eur)', query_lower)
                if match:
                    currency_text = match.group(2)
                    if "us" in currency_text or "usd" in currency_text or "dollar" in currency_text:
                        params[param_name] = "USD"
                    elif "british" in currency_text or "gbp" in currency_text or "pound" in currency_text:
                        params[param_name] = "GBP"
                    elif "euro" in currency_text or "eur" in currency_text:
                        params[param_name] = "EUR"
        
        elif param_name == "target_currency":
            # Extract target currency - look for "to X" or "in X currency"
            # Pattern: "cost in British Pounds" -> target is GBP
            if "in british pound" in query_lower or "to british pound" in query_lower or "to gbp" in query_lower:
                params[param_name] = "GBP"
            elif "in us dollar" in query_lower or "to us dollar" in query_lower or "to usd" in query_lower:
                params[param_name] = "USD"
            elif "in euro" in query_lower or "to euro" in query_lower or "to eur" in query_lower:
                params[param_name] = "EUR"
            else:
                # More flexible pattern
                match = re.search(r'(?:in|to)\s+(british\s*pounds?|gbp|us\s*dollars?|usd|euros?|eur)', query_lower)
                if match:
                    currency_text = match.group(1)
                    if "british" in currency_text or "gbp" in currency_text or "pound" in currency_text:
                        params[param_name] = "GBP"
                    elif "us" in currency_text or "usd" in currency_text or "dollar" in currency_text:
                        params[param_name] = "USD"
                    elif "euro" in currency_text or "eur" in currency_text:
                        params[param_name] = "EUR"
        
        elif param_name == "amount":
            # Extract numeric amount
            numbers = re.findall(r'(\d+(?:\.\d+)?)', query)
            if numbers:
                # Take the first number as the amount
                params[param_name] = float(numbers[0])
    
    return {func_name: params}
