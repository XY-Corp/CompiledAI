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
    """Extract function name and parameters from user query using regex patterns."""
    
    # Parse prompt - may be JSON string with nested structure
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
            # Handle BFCL format: {"question": [[{"role": "user", "content": "..."}]], ...}
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
    
    # Extract all numbers from the query
    numbers = re.findall(r'\d+(?:\.\d+)?', query)
    
    # Build parameters based on schema
    params = {}
    num_idx = 0
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        
        if param_type in ["integer", "number", "float"]:
            if num_idx < len(numbers):
                if param_type == "integer":
                    params[param_name] = int(float(numbers[num_idx]))
                else:
                    params[param_name] = float(numbers[num_idx])
                num_idx += 1
        elif param_type == "string":
            # Check if there's a default mentioned in description
            description = param_info.get("description", "")
            default_match = re.search(r'[Dd]efault\s+(?:is\s+)?["\']?([^"\'\.]+)["\']?', description)
            
            # Look for explicit unit mentions in query
            unit_patterns = [
                r'(?:in|using|with)\s+(?:units?\s+(?:of\s+)?)?([a-zA-Z³/]+)',
                r'([a-zA-Z]+/[a-zA-Z³]+)',
            ]
            
            unit_found = None
            for pattern in unit_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    unit_found = match.group(1)
                    break
            
            # Only include if explicitly mentioned or required
            # For optional params like 'unit', don't include unless specified
            if param_name not in func.get("parameters", {}).get("required", []):
                # Optional param - only include if explicitly mentioned in query
                if unit_found:
                    params[param_name] = unit_found
                # Otherwise skip optional params
            else:
                # Required string param
                if unit_found:
                    params[param_name] = unit_found
                else:
                    # Try to extract from query context
                    string_match = re.search(r'(?:for|in|of|with)\s+([A-Za-z\s]+?)(?:\s+(?:and|with|,)|$)', query, re.IGNORECASE)
                    if string_match:
                        params[param_name] = string_match.group(1).strip()
    
    return {func_name: params}
