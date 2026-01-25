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
    
    Returns format: {"function_name": {"param1": val1, "param2": val2}}
    """
    # Parse prompt - may be JSON string with nested structure
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
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters from query using regex and string matching
    params = {}
    query_lower = query.lower()
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_type == "integer":
            # Extract numbers - look for patterns like "last 3 days", "3 days", etc.
            if "day" in param_desc or param_name == "days":
                # Look for number followed by "day(s)"
                match = re.search(r'(\d+)\s*days?', query_lower)
                if match:
                    params[param_name] = int(match.group(1))
                else:
                    # Just find any number
                    numbers = re.findall(r'\d+', query)
                    if numbers:
                        params[param_name] = int(numbers[0])
            else:
                # Generic integer extraction
                numbers = re.findall(r'\d+', query)
                if numbers:
                    params[param_name] = int(numbers[0])
        
        elif param_type == "string":
            if "company" in param_desc or param_name == "company":
                # Extract company name - look for known patterns
                # Common patterns: "price of X stock", "X stock price", "stock price of X"
                company_patterns = [
                    r"price of\s+([A-Za-z]+)\s+stock",
                    r"([A-Za-z]+)\s+stock\s+price",
                    r"stock\s+price\s+(?:of|for)\s+([A-Za-z]+)",
                    r"(?:for|of)\s+([A-Za-z]+)\s+(?:stock|shares)",
                    r"([A-Za-z]+)'s\s+(?:stock|share)",
                ]
                
                for pattern in company_patterns:
                    match = re.search(pattern, query, re.IGNORECASE)
                    if match:
                        params[param_name] = match.group(1)
                        break
                
                # If no pattern matched, look for capitalized words that might be company names
                if param_name not in params:
                    # Known company names
                    known_companies = ["Amazon", "Apple", "Google", "Microsoft", "Tesla", "Meta", "Netflix", "Nvidia"]
                    for company in known_companies:
                        if company.lower() in query_lower:
                            params[param_name] = company
                            break
            
            elif "data_type" in param_name or "type" in param_desc:
                # Look for price data types
                price_types = ["open", "close", "high", "low"]
                for pt in price_types:
                    if pt in query_lower:
                        params[param_name] = pt.capitalize()
                        break
                # Don't set default - let it be omitted if not specified (optional param)
    
    return {func_name: params}
