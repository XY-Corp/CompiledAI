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
    """Extract function name and parameters from user query using regex patterns.
    
    Returns a dict with function name as key and parameters as nested object.
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
    required_params = func.get("parameters", {}).get("required", [])
    
    # Extract parameters using regex
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_type == "integer" or param_type == "number":
            # Extract numbers from query
            # Look for patterns like "radius 3", "radius of 3", "radius: 3", or just numbers
            
            # Try specific patterns first based on param name
            specific_patterns = [
                rf'{param_name}\s*(?:of|is|=|:)?\s*(\d+(?:\.\d+)?)',
                rf'(?:with|has)\s+{param_name}\s+(\d+(?:\.\d+)?)',
                rf'(\d+(?:\.\d+)?)\s*{param_name}',
            ]
            
            value = None
            for pattern in specific_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    value = match.group(1)
                    break
            
            # Fallback: extract all numbers and use the first one for required params
            if value is None and param_name in required_params:
                numbers = re.findall(r'\d+(?:\.\d+)?', query)
                if numbers:
                    value = numbers[0]
            
            if value is not None:
                if param_type == "integer":
                    params[param_name] = int(float(value))
                else:
                    params[param_name] = float(value)
        
        elif param_type == "string":
            # For string params, look for explicit mentions or use defaults
            # Check if there's a default mentioned in description
            default_match = re.search(r"default\s+(?:is\s+)?['\"]?(\w+)['\"]?", param_desc, re.IGNORECASE)
            
            # Look for explicit value in query
            string_patterns = [
                rf'{param_name}\s*(?:of|is|=|:)?\s*["\']?(\w+)["\']?',
                rf'in\s+(\w+)\s*{param_name}',
            ]
            
            value = None
            for pattern in string_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    value = match.group(1)
                    break
            
            # Only include if explicitly mentioned in query (don't add defaults for optional params)
            if value is not None:
                params[param_name] = value
    
    return {func_name: params}
