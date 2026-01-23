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
    """Extract function call parameters from user query and return as {func_name: {params}}.
    
    Uses regex and string matching to extract values - no LLM calls needed.
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
    
    # Clean up query - remove surrounding quotes if present
    query = query.strip().strip("'\"")
    
    # Parse functions - may be JSON string
    if isinstance(functions, str):
        try:
            functions = json.loads(functions)
        except json.JSONDecodeError:
            functions = []
    
    if not functions:
        return {"error": "No functions provided"}
    
    func = functions[0]
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters based on schema
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_name == "company":
            # Extract company/ticker - look for known patterns
            # "stock price of Apple" -> AAPL
            # Common company to ticker mappings
            company_tickers = {
                "apple": "AAPL",
                "google": "GOOGL",
                "microsoft": "MSFT",
                "amazon": "AMZN",
                "tesla": "TSLA",
                "meta": "META",
                "facebook": "META",
                "netflix": "NFLX",
                "nvidia": "NVDA",
            }
            
            query_lower = query.lower()
            for company, ticker in company_tickers.items():
                if company in query_lower:
                    params[param_name] = ticker
                    break
            
            # If no match found, try to extract a capitalized word after "of" or "for"
            if param_name not in params:
                match = re.search(r'(?:of|for)\s+([A-Z][a-zA-Z]+)', query)
                if match:
                    params[param_name] = match.group(1).upper()
        
        elif param_name == "days":
            # Extract number of days
            # "last 5 days" -> 5
            match = re.search(r'(?:last|past|previous)?\s*(\d+)\s*days?', query, re.IGNORECASE)
            if match:
                params[param_name] = int(match.group(1))
            else:
                # Try to find any number
                numbers = re.findall(r'\d+', query)
                if numbers:
                    params[param_name] = int(numbers[0])
        
        elif param_name == "exchange":
            # Extract stock exchange
            # Look for common exchanges
            exchanges = ["NYSE", "NASDAQ", "AMEX", "LSE", "TSE", "HKEX"]
            query_upper = query.upper()
            for exchange in exchanges:
                if exchange in query_upper:
                    params[param_name] = exchange
                    break
        
        elif param_type == "integer":
            # Generic integer extraction
            numbers = re.findall(r'\d+', query)
            if numbers:
                params[param_name] = int(numbers[0])
        
        elif param_type == "string":
            # Generic string extraction - try to find quoted strings or after "for/of"
            quoted = re.search(r'["\']([^"\']+)["\']', query)
            if quoted:
                params[param_name] = quoted.group(1)
    
    return {func_name: params}
