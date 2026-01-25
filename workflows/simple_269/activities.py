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
    """Extract function name and parameters from user query using regex patterns."""
    
    # Parse prompt - may be JSON string with nested structure
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
            # Handle BFCL format: {"question": [[{"role": "user", "content": "..."}]], ...}
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
    
    # Extract parameters using regex
    params = {}
    
    # Extract all numbers (integers and floats) from the query
    # Pattern matches: $10,000 or 10000 or 5% or 10 years etc.
    numbers = []
    
    # Extract dollar amounts (e.g., $10,000)
    dollar_match = re.search(r'\$[\d,]+(?:\.\d+)?', query)
    if dollar_match:
        dollar_val = dollar_match.group(0).replace('$', '').replace(',', '')
        numbers.append(('dollar', float(dollar_val)))
    
    # Extract percentages (e.g., 5%)
    percent_match = re.search(r'(\d+(?:\.\d+)?)\s*%', query)
    if percent_match:
        percent_val = float(percent_match.group(1))
        numbers.append(('percent', percent_val))
    
    # Extract years (e.g., 10 years)
    years_match = re.search(r'(\d+)\s*years?', query, re.IGNORECASE)
    if years_match:
        years_val = int(years_match.group(1))
        numbers.append(('years', years_val))
    
    # Extract compounding frequency
    compounds_per_year = 1  # Default
    if re.search(r'compound(?:ed)?\s+(?:yearly|annually)', query, re.IGNORECASE):
        compounds_per_year = 1
    elif re.search(r'compound(?:ed)?\s+(?:semi-?annually|twice\s+(?:a|per)\s+year)', query, re.IGNORECASE):
        compounds_per_year = 2
    elif re.search(r'compound(?:ed)?\s+(?:quarterly|four\s+times)', query, re.IGNORECASE):
        compounds_per_year = 4
    elif re.search(r'compound(?:ed)?\s+(?:monthly)', query, re.IGNORECASE):
        compounds_per_year = 12
    elif re.search(r'compound(?:ed)?\s+(?:daily)', query, re.IGNORECASE):
        compounds_per_year = 365
    
    # Map extracted values to parameter names based on schema
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_name == "principle" or "initial" in param_desc or "investment" in param_desc:
            # Look for dollar amount
            for num_type, num_val in numbers:
                if num_type == 'dollar':
                    params[param_name] = int(num_val) if param_type == "integer" else num_val
                    break
        
        elif param_name == "interest_rate" or "rate" in param_desc:
            # Look for percentage - convert to decimal (5% -> 0.05)
            for num_type, num_val in numbers:
                if num_type == 'percent':
                    # Convert percentage to decimal form (5% -> 0.05)
                    params[param_name] = num_val / 100.0
                    break
        
        elif param_name == "time" or "years" in param_desc or "time" in param_desc:
            # Look for years
            for num_type, num_val in numbers:
                if num_type == 'years':
                    params[param_name] = int(num_val) if param_type == "integer" else num_val
                    break
        
        elif param_name == "compounds_per_year" or "compounded" in param_desc:
            params[param_name] = compounds_per_year
    
    return {func_name: params}
