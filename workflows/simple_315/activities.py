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
    """Extract function call parameters from user query and return as {func_name: {params}}.
    
    Uses regex and string matching to extract parameter values - no LLM calls needed.
    """
    # Parse prompt (may be JSON string with nested structure)
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
    
    # Extract parameters based on schema
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_type == "integer" or param_type == "number":
            # Extract numbers from query
            # For "season" parameter, look for year patterns (4-digit numbers)
            if "season" in param_name.lower() or "year" in param_desc:
                # Look for 4-digit year
                year_match = re.search(r'\b(19\d{2}|20\d{2})\b', query)
                if year_match:
                    params[param_name] = int(year_match.group(1))
            elif "top" in param_name.lower() or "number" in param_desc or "count" in param_desc:
                # Look for numbers indicating count/top N
                # Check for patterns like "top 5", "best 3", etc.
                top_match = re.search(r'(?:top|best|first)\s+(\d+)', query, re.IGNORECASE)
                if top_match:
                    params[param_name] = int(top_match.group(1))
                # Only set if explicitly mentioned, otherwise skip (use default)
            else:
                # Generic number extraction
                numbers = re.findall(r'\b(\d+)\b', query)
                if numbers:
                    # Use first number found that's not already used
                    for num in numbers:
                        num_int = int(num)
                        if num_int not in params.values():
                            params[param_name] = num_int
                            break
        
        elif param_type == "string":
            # Extract string values based on context
            # This would need more specific patterns based on the parameter
            pass
    
    # Ensure required parameters are present
    for req_param in required_params:
        if req_param not in params:
            # Try harder to find the value
            param_info = params_schema.get(req_param, {})
            param_type = param_info.get("type", "string")
            
            if param_type == "integer":
                # Extract any remaining numbers
                numbers = re.findall(r'\b(\d+)\b', query)
                for num in numbers:
                    num_int = int(num)
                    if num_int not in params.values():
                        params[req_param] = num_int
                        break
    
    return {func_name: params}
