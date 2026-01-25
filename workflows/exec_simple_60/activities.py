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
    """Extract function name and parameters from user query.
    
    Parses the prompt to extract the user's query, identifies the target function,
    and extracts parameter values using regex patterns.
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
    
    # Get target function details
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters based on schema
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        
        if param_name == "ip_address" or "ip" in param_name.lower():
            # Extract IP address using regex pattern
            ip_pattern = r'\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b'
            ip_match = re.search(ip_pattern, query)
            if ip_match:
                params[param_name] = ip_match.group(1)
        elif param_type == "integer" or param_type == "number":
            # Extract numbers
            numbers = re.findall(r'\b(\d+)\b', query)
            if numbers:
                params[param_name] = int(numbers[0]) if param_type == "integer" else float(numbers[0])
        elif param_type == "string":
            # For generic string params, try common patterns
            # Pattern: "for X" or "in X" or "of X"
            string_match = re.search(r'(?:for|in|of|with)\s+([A-Za-z0-9\s\.\-]+?)(?:\s+(?:and|with|,|to|\.|$))', query, re.IGNORECASE)
            if string_match:
                params[param_name] = string_match.group(1).strip()
    
    return {func_name: params}
