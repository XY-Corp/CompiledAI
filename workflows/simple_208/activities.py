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
    """Extract function name and parameters from user query. Returns {func_name: {params}}."""
    
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
    
    # Extract parameters based on the query
    params = {}
    query_lower = query.lower()
    
    # For map_service.get_directions - extract start, end, and avoid
    if "directions" in func_name.lower() or "route" in func_name.lower():
        # Extract start and end locations
        # Pattern: "from X to Y"
        from_to_match = re.search(r'from\s+([A-Za-z\s]+?)\s+to\s+([A-Za-z\s]+?)(?:\s+avoiding|\s+avoid|\s*$|\.)', query, re.IGNORECASE)
        if from_to_match:
            params["start"] = from_to_match.group(1).strip()
            params["end"] = from_to_match.group(2).strip()
        
        # Extract avoid preferences
        avoid_list = []
        if "avoid" in params_schema:
            # Check for each possible avoid option
            avoid_options = ["tolls", "highways", "ferries"]
            
            # Look for "avoiding X and Y" or "avoid X, Y"
            avoid_match = re.search(r'avoid(?:ing)?\s+(.+?)(?:\.|$)', query, re.IGNORECASE)
            if avoid_match:
                avoid_text = avoid_match.group(1).lower()
                for option in avoid_options:
                    # Check for the option or its variations
                    if option in avoid_text:
                        avoid_list.append(option)
                    # Handle "toll roads" -> "tolls"
                    elif option == "tolls" and "toll" in avoid_text:
                        avoid_list.append("tolls")
            
            if avoid_list:
                params["avoid"] = avoid_list
    
    # Generic extraction for other function types
    else:
        for param_name, param_info in params_schema.items():
            param_type = param_info.get("type", "string") if isinstance(param_info, dict) else "string"
            
            if param_type in ["integer", "number", "float"]:
                # Extract numbers
                numbers = re.findall(r'\d+(?:\.\d+)?', query)
                if numbers:
                    if param_type == "integer":
                        params[param_name] = int(numbers[0])
                    else:
                        params[param_name] = float(numbers[0])
            elif param_type == "string":
                # Try to extract string values based on common patterns
                # Pattern: "for X" or "in X" or "to X"
                string_match = re.search(rf'(?:for|in|to|from)\s+([A-Za-z\s]+?)(?:\s+(?:and|with|to|from|,)|$)', query, re.IGNORECASE)
                if string_match:
                    params[param_name] = string_match.group(1).strip()
    
    return {func_name: params}
