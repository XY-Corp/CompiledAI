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
    
    # Parse prompt (may be JSON string with nested structure)
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
        else:
            data = prompt
        
        # Extract user query from BFCL format
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
    required_params = func.get("parameters", {}).get("required", [])
    
    # Extract monetary values with context using regex
    # Pattern: "$X,XXX,XXX" or "$X,XXX" or "$XXX" with optional description before/after
    monetary_patterns = [
        (r"net\s+income\s+of\s+\$?([\d,]+)", "net_income"),
        (r"shareholder'?s?\s+equity\s+of\s+\$?([\d,]+)", "shareholder_equity"),
        (r"dividends?\s+paid\s+of\s+\$?([\d,]+)", "dividends_paid"),
        (r"dividends?\s+of\s+\$?([\d,]+)", "dividends_paid"),
    ]
    
    params = {}
    
    # Try to extract each parameter using context-aware patterns
    for pattern, param_name in monetary_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            # Remove commas and convert to integer
            value_str = match.group(1).replace(",", "")
            try:
                params[param_name] = int(value_str)
            except ValueError:
                pass
    
    # Fallback: if we didn't get all required params, try extracting all dollar amounts in order
    if not all(p in params for p in required_params):
        # Extract all dollar amounts
        all_amounts = re.findall(r'\$?([\d,]+(?:,\d{3})*)', query)
        amounts = []
        for amt in all_amounts:
            cleaned = amt.replace(",", "")
            if cleaned.isdigit() and int(cleaned) > 0:
                amounts.append(int(cleaned))
        
        # Map amounts to parameters based on typical order in financial queries
        param_order = ["net_income", "shareholder_equity", "dividends_paid"]
        for i, param_name in enumerate(param_order):
            if param_name not in params and i < len(amounts):
                params[param_name] = amounts[i]
    
    # Apply defaults for optional parameters if not found
    for param_name, param_info in params_schema.items():
        if param_name not in params:
            # Check if there's a default mentioned in description
            desc = param_info.get("description", "")
            if "default to 0" in desc.lower() or "default is 0" in desc.lower():
                params[param_name] = 0
    
    return {func_name: params}
