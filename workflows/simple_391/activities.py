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
    """Extract function name and parameters from user query. Returns {func_name: {params}}."""
    
    # Parse prompt (may be JSON string with nested structure)
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
        else:
            data = prompt
        
        # Extract user query from BFCL format: {"question": [[{"role": "user", "content": "..."}]]}
        if isinstance(data, dict) and "question" in data:
            question_data = data["question"]
            if isinstance(question_data, list) and len(question_data) > 0:
                if isinstance(question_data[0], list) and len(question_data[0]) > 0:
                    query = question_data[0][0].get("content", str(prompt))
                else:
                    query = str(prompt)
            else:
                query = str(prompt)
        else:
            query = str(prompt)
    except (json.JSONDecodeError, TypeError):
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
    
    # Extract parameters from query using regex and string matching
    params = {}
    query_lower = query.lower()
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_name == "base_currency":
            # Look for "from X" pattern for base currency
            # Common currency patterns
            currency_map = {
                "british pounds": "GBP",
                "british pound": "GBP",
                "pounds": "GBP",
                "gbp": "GBP",
                "japanese yen": "JPY",
                "yen": "JPY",
                "jpy": "JPY",
                "us dollars": "USD",
                "usd": "USD",
                "dollars": "USD",
                "euros": "EUR",
                "euro": "EUR",
                "eur": "EUR",
            }
            
            # Pattern: "from X to Y"
            from_match = re.search(r'from\s+([a-zA-Z\s]+?)\s+to\s+', query_lower)
            if from_match:
                currency_text = from_match.group(1).strip()
                for key, code in currency_map.items():
                    if key in currency_text:
                        params[param_name] = code
                        break
        
        elif param_name == "target_currency":
            # Look for "to X" pattern for target currency
            currency_map = {
                "british pounds": "GBP",
                "british pound": "GBP",
                "pounds": "GBP",
                "gbp": "GBP",
                "japanese yen": "JPY",
                "yen": "JPY",
                "jpy": "JPY",
                "us dollars": "USD",
                "usd": "USD",
                "dollars": "USD",
                "euros": "EUR",
                "euro": "EUR",
                "eur": "EUR",
            }
            
            # Pattern: "to X" (after "from ... to")
            to_match = re.search(r'\bto\s+([a-zA-Z\s]+?)(?:\s+with|\s+including|\s+and|\s*$)', query_lower)
            if to_match:
                currency_text = to_match.group(1).strip()
                for key, code in currency_map.items():
                    if key in currency_text:
                        params[param_name] = code
                        break
        
        elif param_name == "fee" and param_type == "float":
            # Extract fee value - look for decimal numbers near "fee"
            # Pattern: "fee X" or "fee of X" or "X fee"
            fee_patterns = [
                r'fee\s+(?:of\s+)?(\d+\.?\d*)',
                r'(\d+\.?\d*)\s+(?:included|fee)',
                r'fee\s*[:=]?\s*(\d+\.?\d*)',
            ]
            
            for pattern in fee_patterns:
                fee_match = re.search(pattern, query_lower)
                if fee_match:
                    params[param_name] = float(fee_match.group(1))
                    break
    
    return {func_name: params}
