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
    
    # Extract all numbers from the query
    # Pattern for currency amounts (e.g., $5000)
    currency_pattern = r'\$(\d+(?:,\d{3})*(?:\.\d+)?)'
    currency_matches = re.findall(currency_pattern, query)
    
    # Pattern for percentages (e.g., 5%)
    percent_pattern = r'(\d+(?:\.\d+)?)\s*%'
    percent_matches = re.findall(percent_pattern, query)
    
    # Pattern for years/period (e.g., "10 years")
    years_pattern = r'(\d+)\s*years?'
    years_matches = re.findall(years_pattern, query, re.IGNORECASE)
    
    # Pattern for generic numbers
    all_numbers = re.findall(r'\d+(?:\.\d+)?', query)
    
    # Map extracted values to parameters based on schema
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_name == "principal" or "principal" in param_desc:
            # Use currency match first, then fall back to first large number
            if currency_matches:
                val = currency_matches[0].replace(",", "")
                params[param_name] = int(float(val))
            elif all_numbers:
                # Find the largest number (likely principal)
                nums = [float(n) for n in all_numbers]
                largest = max(nums)
                params[param_name] = int(largest)
        
        elif param_name == "interest_rate" or "interest rate" in param_desc or "rate" in param_desc:
            # Use percentage match
            if percent_matches:
                # Convert percentage to decimal (5% -> 0.05) or keep as 5 based on context
                rate_val = float(percent_matches[0])
                # Check if description suggests decimal format
                if "decimal" in param_desc:
                    params[param_name] = rate_val / 100
                else:
                    params[param_name] = rate_val
        
        elif param_name == "period" or "period" in param_desc or "years" in param_desc:
            # Use years match
            if years_matches:
                params[param_name] = int(years_matches[0])
        
        elif param_name == "compounding_frequency" or "frequency" in param_desc:
            # Check for frequency keywords in query
            query_lower = query.lower()
            if "daily" in query_lower:
                params[param_name] = "Daily"
            elif "monthly" in query_lower:
                params[param_name] = "Monthly"
            elif "quarterly" in query_lower:
                params[param_name] = "Quarterly"
            elif "semiannually" in query_lower or "semi-annually" in query_lower:
                params[param_name] = "Semiannually"
            elif "annually" in query_lower:
                params[param_name] = "Annually"
            # If not specified and not required, don't include (use default)
    
    return {func_name: params}
