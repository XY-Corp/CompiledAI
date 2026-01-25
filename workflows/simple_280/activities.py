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
    
    # Extract parameters from query
    params = {}
    query_lower = query.lower()
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_name == "budget" or "budget" in param_desc:
            # Extract budget - look for dollar amounts or numbers after "budget"
            budget_patterns = [
                r'\$(\d+(?:,\d{3})*(?:\.\d{2})?)',  # $1000 or $1,000.00
                r'budget\s+(?:of\s+)?\$?(\d+(?:,\d{3})*)',  # budget of $1000 or budget 1000
                r'(\d+(?:,\d{3})*)\s*(?:dollars?|usd)',  # 1000 dollars
            ]
            for pattern in budget_patterns:
                match = re.search(pattern, query_lower.replace(',', ''))
                if match:
                    params[param_name] = int(match.group(1).replace(',', ''))
                    break
            
            # Fallback: find any number that looks like a budget
            if param_name not in params:
                numbers = re.findall(r'\d+', query)
                for num in numbers:
                    if int(num) >= 100:  # Likely a budget amount
                        params[param_name] = int(num)
                        break
        
        elif param_name == "type" or "type" in param_desc:
            # Extract instrument type - look for common instrument types or descriptors
            type_patterns = [
                r'(acoustic|electric|classical|bass|digital|keyboard|wind|string|percussion)',
                r'(guitar|piano|violin|drums?|flute|saxophone|trumpet|cello)',
            ]
            for pattern in type_patterns:
                match = re.search(pattern, query_lower)
                if match:
                    params[param_name] = match.group(1)
                    break
        
        elif param_name == "make" or "maker" in param_desc:
            # Extract maker/brand - look for known brands or "by X" pattern
            make_patterns = [
                r'(?:by|from|made by)\s+([A-Z][a-zA-Z]+)',
                r'(fender|gibson|yamaha|roland|steinway|taylor|martin|ibanez)',
            ]
            for pattern in make_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    params[param_name] = match.group(1)
                    break
            # Don't include make if not specified (it's optional with default)
    
    return {func_name: params}
