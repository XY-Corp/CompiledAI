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
            # Extract user query from BFCL format: {"question": [[{"role": "user", "content": "..."}]]}
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
    
    # Extract all numbers from the query
    # Pattern for percentages (e.g., "5%", "5 percent", "5.5%")
    percentage_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:%|percent)', query, re.IGNORECASE)
    
    # Pattern for dollar amounts (e.g., "$2000", "2000 dollars")
    dollar_match = re.search(r'\$\s*(\d+(?:,\d{3})*(?:\.\d+)?)|(\d+(?:,\d{3})*(?:\.\d+)?)\s*dollars?', query, re.IGNORECASE)
    
    # Pattern for years (e.g., "3 years", "3-year")
    years_match = re.search(r'(\d+)\s*(?:years?|yr)', query, re.IGNORECASE)
    
    # Map extracted values to parameter names based on schema
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        # Match based on parameter name and description
        if "yield" in param_name.lower() or "yield" in param_desc or "percentage" in param_desc:
            if percentage_match:
                value = float(percentage_match.group(1))
                params[param_name] = value
        elif "amount" in param_name.lower() or "investment" in param_name.lower() or "amount" in param_desc:
            if dollar_match:
                # Get the matched group (either $X or X dollars)
                value_str = dollar_match.group(1) or dollar_match.group(2)
                value_str = value_str.replace(",", "")
                if param_type == "integer":
                    params[param_name] = int(float(value_str))
                else:
                    params[param_name] = float(value_str)
        elif "year" in param_name.lower() or "time" in param_name.lower() or "period" in param_desc or "year" in param_desc:
            if years_match:
                value = int(years_match.group(1))
                params[param_name] = value
    
    return {func_name: params}
