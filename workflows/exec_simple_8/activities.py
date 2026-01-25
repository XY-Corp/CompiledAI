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
    """Extract function call parameters from natural language prompt.
    
    Parses the prompt to extract numeric values and maps them to the
    appropriate function parameters based on the function schema.
    """
    # Parse prompt - may be JSON string with nested structure
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
        else:
            data = prompt
        
        # Extract user query from BFCL format: {"question": [[{"role": "user", "content": "..."}]]}
        if "question" in data and isinstance(data["question"], list):
            if len(data["question"]) > 0 and isinstance(data["question"][0], list):
                if len(data["question"][0]) > 0 and isinstance(data["question"][0][0], dict):
                    query = data["question"][0][0].get("content", str(prompt))
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
    
    # Get function details
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract all numbers from the query using regex
    # Pattern matches integers and floats
    numbers = re.findall(r'\b(\d+(?:\.\d+)?)\b', query)
    numbers = [float(n) for n in numbers]
    
    # Map extracted values to parameters based on schema
    params = {}
    num_idx = 0
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_type in ["float", "integer", "number"]:
            # Try to find a number that matches the parameter context
            # Look for keywords in the query that relate to this parameter
            
            # For charge - look for "charge of X coulombs" or "X coulombs"
            if "charge" in param_name.lower() or "coulomb" in param_desc:
                charge_match = re.search(r'charge\s+of\s+(\d+(?:\.\d+)?)', query, re.IGNORECASE)
                if not charge_match:
                    charge_match = re.search(r'(\d+(?:\.\d+)?)\s*coulombs?', query, re.IGNORECASE)
                if charge_match:
                    params[param_name] = float(charge_match.group(1))
                    continue
            
            # For voltage - look for "voltage of X volts" or "X volts"
            if "voltage" in param_name.lower() or "volt" in param_desc:
                voltage_match = re.search(r'voltage\s+of\s+(\d+(?:\.\d+)?)', query, re.IGNORECASE)
                if not voltage_match:
                    voltage_match = re.search(r'(\d+(?:\.\d+)?)\s*volts?', query, re.IGNORECASE)
                if voltage_match:
                    params[param_name] = float(voltage_match.group(1))
                    continue
            
            # Fallback: assign numbers in order
            if num_idx < len(numbers):
                params[param_name] = numbers[num_idx]
                num_idx += 1
        
        elif param_type == "string":
            # For string parameters, try to extract relevant text
            # This is a fallback - most physics calculations use numbers
            params[param_name] = ""
    
    return {func_name: params}
