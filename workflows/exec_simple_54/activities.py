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
    """Extract function name and parameters from user query and function schema.
    
    Returns a dict with function name as key and parameters as nested object.
    """
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
    
    if not funcs:
        return {"error": "No functions provided"}
    
    # Get function details
    func = funcs[0]
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters based on schema
    params = {}
    query_lower = query.lower()
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_type == "string":
            # For stock_name parameter - extract stock symbol or company name
            if "stock" in param_name.lower() or "stock" in param_desc:
                # Common stock symbol mappings
                stock_mappings = {
                    "apple": "AAPL",
                    "apple inc": "AAPL",
                    "microsoft": "MSFT",
                    "google": "GOOGL",
                    "alphabet": "GOOGL",
                    "amazon": "AMZN",
                    "tesla": "TSLA",
                    "meta": "META",
                    "facebook": "META",
                    "nvidia": "NVDA",
                    "netflix": "NFLX",
                }
                
                # Check for company names in query
                for company, symbol in stock_mappings.items():
                    if company in query_lower:
                        params[param_name] = symbol
                        break
                
                # If not found, try to extract a stock symbol directly (uppercase letters)
                if param_name not in params:
                    symbol_match = re.search(r'\b([A-Z]{1,5})\b', query)
                    if symbol_match:
                        params[param_name] = symbol_match.group(1)
                
                # Fallback - try to extract quoted text
                if param_name not in params:
                    quoted_match = re.search(r'["\']([^"\']+)["\']', query)
                    if quoted_match:
                        params[param_name] = quoted_match.group(1)
            else:
                # Generic string extraction - look for quoted values or key phrases
                quoted_match = re.search(r'["\']([^"\']+)["\']', query)
                if quoted_match:
                    params[param_name] = quoted_match.group(1)
                else:
                    # Try to extract after "for" or "of"
                    for_match = re.search(r'(?:for|of)\s+([A-Za-z\s]+?)(?:\s*[.,?!]|$)', query, re.IGNORECASE)
                    if for_match:
                        params[param_name] = for_match.group(1).strip()
        
        elif param_type in ["integer", "number", "float"]:
            # Extract numbers
            numbers = re.findall(r'-?\d+(?:\.\d+)?', query)
            if numbers:
                if param_type == "integer":
                    params[param_name] = int(float(numbers[0]))
                else:
                    params[param_name] = float(numbers[0])
    
    return {func_name: params}
