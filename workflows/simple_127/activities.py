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
    """Extract function call parameters from natural language query.
    
    Parses the prompt to extract the function name and parameters,
    returning them in the format {"function_name": {"param1": val1}}.
    """
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
    props = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters using regex and string parsing
    params = {}
    
    for param_name, param_info in props.items():
        param_type = param_info.get("type", "string")
        
        if param_name == "cash_flows":
            # Extract array like cash_flows=[200,300,400,500]
            array_match = re.search(r'cash_flows\s*=\s*\[([^\]]+)\]', query)
            if array_match:
                array_str = array_match.group(1)
                # Parse comma-separated integers
                values = [int(x.strip()) for x in array_str.split(',') if x.strip().isdigit() or x.strip().lstrip('-').isdigit()]
                params[param_name] = values
        
        elif param_name == "discount_rate":
            # Extract discount rate - look for percentage or decimal
            # Pattern: "discount rate of 10%" or "discount_rate=0.1" or "10% discount"
            rate_match = re.search(r'discount\s*rate\s*(?:of\s*)?(\d+(?:\.\d+)?)\s*%?', query, re.IGNORECASE)
            if rate_match:
                rate_value = float(rate_match.group(1))
                # If it's a percentage (like 10), convert to decimal (0.1)
                if rate_value > 1:
                    rate_value = rate_value / 100
                params[param_name] = rate_value
            else:
                # Try pattern like "10%"
                pct_match = re.search(r'(\d+(?:\.\d+)?)\s*%', query)
                if pct_match:
                    rate_value = float(pct_match.group(1)) / 100
                    params[param_name] = rate_value
        
        elif param_name == "initial_investment":
            # Extract initial investment - look for "$2000" or "initial investment of 2000"
            inv_match = re.search(r'initial\s*investment\s*(?:of\s*)?\$?(\d+(?:,\d{3})*(?:\.\d+)?)', query, re.IGNORECASE)
            if inv_match:
                # Remove commas and convert to int
                inv_value = int(inv_match.group(1).replace(',', '').split('.')[0])
                params[param_name] = inv_value
            else:
                # Try pattern like "$2000"
                dollar_match = re.search(r'\$(\d+(?:,\d{3})*)', query)
                if dollar_match:
                    inv_value = int(dollar_match.group(1).replace(',', ''))
                    params[param_name] = inv_value
    
    return {func_name: params}
