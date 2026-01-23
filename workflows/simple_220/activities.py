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
    """Extract function call parameters from natural language query using regex.
    
    Returns a dict with function name as key and parameters as nested object.
    """
    # Parse prompt - may be JSON string with nested structure
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
            # Handle BFCL format: {"question": [[{"role": "user", "content": "..."}]]}
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
    
    # Extract parameters using regex patterns
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        
        # Build regex patterns based on parameter name
        # Convert snake_case to readable patterns
        readable_name = param_name.replace("_", " ")
        
        # Try multiple patterns for each parameter
        patterns = [
            # Pattern: "param_name of X" or "param_name X"
            rf'{readable_name}\s+(?:of\s+)?(\d+(?:\.\d+)?)',
            # Pattern: "X param_name"
            rf'(\d+(?:\.\d+)?)\s+{readable_name}',
            # Pattern: "param_name: X" or "param_name = X"
            rf'{readable_name}[:\s=]+(\d+(?:\.\d+)?)',
        ]
        
        value = None
        for pattern in patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                value = match.group(1)
                break
        
        if value is not None:
            # Convert to appropriate type
            if param_type == "integer":
                params[param_name] = int(float(value))
            elif param_type == "float" or param_type == "number":
                params[param_name] = float(value)
            else:
                params[param_name] = value
    
    # If standard patterns didn't work, try extracting all numbers and mapping by context
    if not params or len(params) < len(params_schema):
        # Extract all numbers from the query
        all_numbers = re.findall(r'(\d+(?:\.\d+)?)', query)
        
        # Map numbers to parameters based on context clues in the query
        for param_name, param_info in params_schema.items():
            if param_name in params:
                continue  # Already extracted
            
            param_type = param_info.get("type", "string")
            readable_name = param_name.replace("_", " ")
            
            # Find the number that appears closest to the parameter name mention
            # Look for patterns like "synaptic input rate of 200"
            for num in all_numbers:
                # Check if this number appears near the parameter name
                pattern = rf'{readable_name}[^0-9]*{re.escape(num)}|{re.escape(num)}[^0-9]*{readable_name}'
                if re.search(pattern, query, re.IGNORECASE):
                    if param_type == "integer":
                        params[param_name] = int(float(num))
                    elif param_type == "float" or param_type == "number":
                        params[param_name] = float(num)
                    else:
                        params[param_name] = num
                    all_numbers.remove(num)
                    break
        
        # Special handling for common parameter patterns
        # "weight 0.5" or "weight of 0.5"
        weight_match = re.search(r'weight\s+(?:of\s+)?(\d+(?:\.\d+)?)', query, re.IGNORECASE)
        if weight_match and "weight" in params_schema and "weight" not in params:
            val = weight_match.group(1)
            params["weight"] = float(val) if params_schema["weight"].get("type") in ["float", "number"] else val
        
        # "decay rate of 0.1" or "decay rate 0.1"
        decay_match = re.search(r'decay\s+rate\s+(?:of\s+)?(\d+(?:\.\d+)?)', query, re.IGNORECASE)
        if decay_match and "decay_rate" in params_schema and "decay_rate" not in params:
            val = decay_match.group(1)
            params["decay_rate"] = float(val) if params_schema["decay_rate"].get("type") in ["float", "number"] else val
        
        # "synaptic input rate of 200" or "input rate of 200"
        input_match = re.search(r'(?:synaptic\s+)?input\s+rate\s+(?:of\s+)?(\d+(?:\.\d+)?)', query, re.IGNORECASE)
        if input_match and "input_synaptic_rate" in params_schema and "input_synaptic_rate" not in params:
            val = input_match.group(1)
            params["input_synaptic_rate"] = int(float(val)) if params_schema["input_synaptic_rate"].get("type") == "integer" else val
    
    return {func_name: params}
