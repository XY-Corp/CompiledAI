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
    
    Returns a dict with function name as key and parameters as nested object.
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
    except (json.JSONDecodeError, TypeError, KeyError):
        query = str(prompt)
    
    # Parse functions (may be JSON string)
    if isinstance(functions, str):
        try:
            funcs = json.loads(functions)
        except json.JSONDecodeError:
            funcs = []
    else:
        funcs = functions if functions else []
    
    # Get function schema
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    props = func.get("parameters", {}).get("properties", {})
    
    params = {}
    
    # Extract cash_flows array - look for patterns like [200,300,400,500] or cash_flows=[...]
    cash_flows_match = re.search(r'cash_flows\s*=\s*\[([^\]]+)\]', query)
    if not cash_flows_match:
        # Try to find any array pattern
        cash_flows_match = re.search(r'\[(\d+(?:\s*,\s*\d+)*)\]', query)
    
    if cash_flows_match:
        cash_flows_str = cash_flows_match.group(1)
        cash_flows = [int(x.strip()) for x in cash_flows_str.split(',')]
        params["cash_flows"] = cash_flows
    
    # Extract discount_rate - look for patterns like "discount rate of 10%" or "10%"
    discount_match = re.search(r'discount\s*rate\s*(?:of\s*)?(\d+(?:\.\d+)?)\s*%', query, re.IGNORECASE)
    if not discount_match:
        # Try pattern like "rate of X%"
        discount_match = re.search(r'rate\s*(?:of\s*)?(\d+(?:\.\d+)?)\s*%', query, re.IGNORECASE)
    
    if discount_match:
        # Convert percentage to decimal (10% -> 0.1)
        discount_rate = float(discount_match.group(1)) / 100.0
        params["discount_rate"] = discount_rate
    
    # Extract initial_investment - look for patterns like "$2000" or "initial investment of $2000"
    investment_match = re.search(r'initial\s*investment\s*(?:of\s*)?\$?(\d+(?:,\d{3})*(?:\.\d+)?)', query, re.IGNORECASE)
    if not investment_match:
        # Try pattern like "$X" near "investment"
        investment_match = re.search(r'\$(\d+(?:,\d{3})*(?:\.\d+)?)', query)
    
    if investment_match:
        # Remove commas and convert to int
        investment_str = investment_match.group(1).replace(',', '')
        params["initial_investment"] = int(float(investment_str))
    
    return {func_name: params}
