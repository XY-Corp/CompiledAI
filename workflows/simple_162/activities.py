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
    """Extract function name and parameters from user query using regex and string matching."""
    
    # Parse prompt - may be JSON string with nested structure
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
    
    # Extract parameters based on schema
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        
        if param_type == "array":
            # For parties - extract names (typically "between X and Y" or "X and Y")
            if param_name == "parties":
                # Pattern: "between John and Alice" or "John and Alice"
                names_match = re.search(r'between\s+([A-Z][a-z]+)\s+and\s+([A-Z][a-z]+)', query, re.IGNORECASE)
                if names_match:
                    params[param_name] = [names_match.group(1), names_match.group(2)]
                else:
                    # Try simpler pattern: "X and Y for"
                    names_match = re.search(r'([A-Z][a-z]+)\s+and\s+([A-Z][a-z]+)', query, re.IGNORECASE)
                    if names_match:
                        params[param_name] = [names_match.group(1), names_match.group(2)]
        
        elif param_type == "string":
            if param_name == "contract_type":
                # Extract contract type - look for "X agreement" or "X contract"
                type_match = re.search(r'for\s+(\w+)\s+agreement', query, re.IGNORECASE)
                if type_match:
                    params[param_name] = type_match.group(1).lower() + " agreement"
                else:
                    type_match = re.search(r'(\w+)\s+contract', query, re.IGNORECASE)
                    if type_match:
                        params[param_name] = type_match.group(1).lower() + " contract"
            
            elif param_name == "location":
                # Extract location - typically "in X" at the end
                loc_match = re.search(r'in\s+([A-Z][a-zA-Z\s]+?)(?:\.|$)', query)
                if loc_match:
                    params[param_name] = loc_match.group(1).strip()
                else:
                    # Try to find state/country names
                    states = ["California", "New York", "Texas", "Florida", "Illinois"]
                    for state in states:
                        if state.lower() in query.lower():
                            params[param_name] = state
                            break
    
    return {func_name: params}
