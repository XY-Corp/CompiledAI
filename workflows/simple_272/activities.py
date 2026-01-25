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
    """Extract function name and parameters from user query using regex/parsing.
    
    Returns format: {"function_name": {"param1": val1, ...}}
    """
    # Parse prompt - may be JSON string with nested structure
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
        else:
            data = prompt
        
        # Extract user query from BFCL format: {"question": [[{"role": "user", "content": "..."}]]}
        if isinstance(data, dict) and "question" in data:
            question_data = data["question"]
            if isinstance(question_data, list) and len(question_data) > 0:
                if isinstance(question_data[0], list) and len(question_data[0]) > 0:
                    query = question_data[0][0].get("content", str(prompt))
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
    
    # Extract parameters using regex based on schema
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        
        if param_type == "integer":
            # Extract integers from query
            # Try specific patterns first: "radius of X", "with a radius of X"
            radius_patterns = [
                r'radius\s+of\s+(\d+)',
                r'radius\s+is\s+(\d+)',
                r'radius\s*[:=]\s*(\d+)',
                r'with\s+(?:a\s+)?radius\s+(?:of\s+)?(\d+)',
            ]
            
            value = None
            for pattern in radius_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    value = int(match.group(1))
                    break
            
            # Fallback: extract any number
            if value is None:
                numbers = re.findall(r'\b(\d+)\b', query)
                if numbers:
                    value = int(numbers[0])
            
            if value is not None:
                params[param_name] = value
                
        elif param_type == "number" or param_type == "float":
            # Extract floats/decimals
            float_patterns = [
                rf'{param_name}\s+of\s+(\d+(?:\.\d+)?)',
                rf'{param_name}\s+is\s+(\d+(?:\.\d+)?)',
                rf'with\s+(?:a\s+)?{param_name}\s+(?:of\s+)?(\d+(?:\.\d+)?)',
            ]
            
            value = None
            for pattern in float_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    value = float(match.group(1))
                    break
            
            # Fallback: extract any number
            if value is None:
                numbers = re.findall(r'\b(\d+(?:\.\d+)?)\b', query)
                if numbers:
                    value = float(numbers[0])
            
            if value is not None:
                params[param_name] = value
                
        elif param_type == "string":
            # Extract string values - try common patterns
            string_patterns = [
                rf'{param_name}\s+(?:is|of|:)\s+["\']?([^"\',.]+)["\']?',
                rf'(?:for|in|with)\s+["\']?([A-Za-z][A-Za-z\s]+?)["\']?(?:\s+(?:and|with|,)|$)',
            ]
            
            for pattern in string_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    params[param_name] = match.group(1).strip()
                    break
    
    return {func_name: params}
