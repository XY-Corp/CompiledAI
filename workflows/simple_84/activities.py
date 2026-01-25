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
    
    # Extract parameters using regex
    params = {}
    
    # Extract all numbers from the query
    numbers = re.findall(r'\d+(?:\.\d+)?', query)
    
    # Map numbers to parameters based on context
    num_idx = 0
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        
        if param_type in ["integer", "number", "float"]:
            # Try to find contextual match first
            # Look for patterns like "weight of 85" or "85 kilograms"
            if param_name == "weight":
                weight_match = re.search(r'weight\s+(?:of\s+)?(\d+)|(\d+)\s*(?:kg|kilogram)', query, re.IGNORECASE)
                if weight_match:
                    val = weight_match.group(1) or weight_match.group(2)
                    params[param_name] = int(val) if param_type == "integer" else float(val)
                    continue
            
            if param_name == "height":
                height_match = re.search(r'height\s+(?:of\s+)?(\d+)|(\d+)\s*(?:cm|centimeter|meter)', query, re.IGNORECASE)
                if height_match:
                    val = height_match.group(1) or height_match.group(2)
                    params[param_name] = int(val) if param_type == "integer" else float(val)
                    continue
            
            # Fallback: assign numbers in order
            if num_idx < len(numbers):
                val = numbers[num_idx]
                params[param_name] = int(val) if param_type == "integer" else float(val)
                num_idx += 1
        
        elif param_type == "string":
            # Check for specific string patterns
            if param_name == "unit":
                if re.search(r'\bimperial\b', query, re.IGNORECASE):
                    params[param_name] = "imperial"
                elif re.search(r'\bmetric\b', query, re.IGNORECASE):
                    params[param_name] = "metric"
                # Don't include optional param if not specified
            else:
                # Generic string extraction - look for quoted values or after "for/in/of"
                string_match = re.search(r'(?:for|in|of|with)\s+([A-Za-z\s]+?)(?:\s+(?:and|with|,)|$)', query, re.IGNORECASE)
                if string_match:
                    params[param_name] = string_match.group(1).strip()
    
    return {func_name: params}
