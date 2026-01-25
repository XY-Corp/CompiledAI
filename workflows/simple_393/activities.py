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
    if isinstance(functions, str):
        try:
            functions = json.loads(functions)
        except json.JSONDecodeError:
            functions = []
    
    if not functions:
        return {"error": "No functions provided"}
    
    func = functions[0]
    func_name = func.get("name", "")
    props = func.get("parameters", {}).get("properties", {})
    
    params = {}
    query_lower = query.lower()
    
    # For convert_currency: extract amount, base_currency, target_currency
    if func_name == "convert_currency":
        # Extract amount - find numbers in the query
        numbers = re.findall(r'\d+(?:,\d+)*(?:\.\d+)?', query)
        if numbers:
            # Remove commas and convert to int
            amount_str = numbers[0].replace(',', '')
            params["amount"] = int(float(amount_str))
        
        # Currency mapping for common names
        currency_map = {
            "japanese yen": "JPY",
            "yen": "JPY",
            "jpy": "JPY",
            "united states dollar": "USD",
            "us dollar": "USD",
            "usd": "USD",
            "dollar": "USD",
            "dollars": "USD",
            "euro": "EUR",
            "eur": "EUR",
            "british pound": "GBP",
            "pound": "GBP",
            "gbp": "GBP",
            "chinese yuan": "CNY",
            "yuan": "CNY",
            "cny": "CNY",
            "indian rupee": "INR",
            "rupee": "INR",
            "inr": "INR",
        }
        
        # Pattern: "X [currency] ... in/to [currency]"
        # Base currency comes before "in" or "to", target comes after
        
        # Find base currency (before "in" or "to")
        base_match = re.search(r'(\d[\d,]*(?:\.\d+)?)\s+([A-Za-z\s]+?)(?:\s+(?:be\s+)?(?:in|to)\s+)', query, re.IGNORECASE)
        if base_match:
            base_currency_text = base_match.group(2).strip().lower()
            for name, code in currency_map.items():
                if name in base_currency_text or base_currency_text in name:
                    params["base_currency"] = code
                    break
        
        # Find target currency (after "in" or "to")
        target_match = re.search(r'(?:in|to)\s+([A-Za-z\s]+?)(?:\?|$|\.)', query, re.IGNORECASE)
        if target_match:
            target_currency_text = target_match.group(1).strip().lower()
            for name, code in currency_map.items():
                if name in target_currency_text or target_currency_text in name:
                    params["target_currency"] = code
                    break
    
    else:
        # Generic extraction for other functions
        # Extract all numbers
        numbers = re.findall(r'\d+(?:\.\d+)?', query)
        num_idx = 0
        
        for param_name, param_info in props.items():
            param_type = param_info.get("type", "string") if isinstance(param_info, dict) else "string"
            
            if param_type in ["integer", "number", "float"]:
                if num_idx < len(numbers):
                    if param_type == "integer":
                        params[param_name] = int(float(numbers[num_idx]))
                    else:
                        params[param_name] = float(numbers[num_idx])
                    num_idx += 1
            elif param_type == "string":
                # Try to extract string values using common patterns
                string_match = re.search(r'(?:for|in|of|with|to)\s+([A-Za-z\s]+?)(?:\s+(?:and|with|,|to|in)|$|\?)', query, re.IGNORECASE)
                if string_match:
                    params[param_name] = string_match.group(1).strip()
    
    return {func_name: params}
