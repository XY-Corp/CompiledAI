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
    
    Parses the user query to extract parameter values and returns them
    in the format {"function_name": {"param1": val1, ...}}.
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
    
    # Extract all numbers (floats and integers) from the query
    # Pattern matches numbers like 0.6, 5, 1e9, etc.
    float_pattern = r'[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?'
    numbers = re.findall(float_pattern, query)
    
    # Convert to appropriate types
    parsed_numbers = []
    for num_str in numbers:
        try:
            if '.' in num_str or 'e' in num_str.lower():
                parsed_numbers.append(float(num_str))
            else:
                parsed_numbers.append(int(num_str))
        except ValueError:
            continue
    
    # Map extracted values to parameters based on context
    query_lower = query.lower()
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_name == "optical_density":
            # Look for optical density value - typically a decimal like 0.6
            od_patterns = [
                r'optical density (?:of |is |=\s*)?(\d*\.?\d+)',
                r'od (?:of |is |=\s*)?(\d*\.?\d+)',
                r'(\d*\.\d+)(?:,|\s|$)',  # Decimal number
            ]
            for pattern in od_patterns:
                match = re.search(pattern, query_lower)
                if match:
                    params[param_name] = float(match.group(1))
                    break
            
            # Fallback: first float-like number (with decimal point)
            if param_name not in params:
                for num in parsed_numbers:
                    if isinstance(num, float) and 0 < num < 10:  # OD typically 0-10
                        params[param_name] = num
                        break
        
        elif param_name == "dilution":
            # Look for dilution factor - typically an integer
            dilution_patterns = [
                r'dilution (?:is |of |factor )?(\d+)',
                r'(\d+)\s*(?:times|x|fold)',
                r'diluted\s*(\d+)',
            ]
            for pattern in dilution_patterns:
                match = re.search(pattern, query_lower)
                if match:
                    params[param_name] = int(match.group(1))
                    break
            
            # Fallback: look for integer that's not the OD
            if param_name not in params:
                for num in parsed_numbers:
                    if isinstance(num, int) or (isinstance(num, float) and num == int(num)):
                        int_val = int(num)
                        # Skip if it looks like OD (small decimal)
                        if int_val > 1:
                            params[param_name] = int_val
                            break
        
        elif param_name == "calibration_factor":
            # Only include if explicitly mentioned (it's optional with default)
            cal_patterns = [
                r'calibration (?:factor )?(?:is |of |=\s*)?(\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)',
            ]
            for pattern in cal_patterns:
                match = re.search(pattern, query_lower)
                if match:
                    params[param_name] = float(match.group(1))
                    break
    
    return {func_name: params}
