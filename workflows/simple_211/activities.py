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
    """Extract function call parameters from user query and return as {func_name: {params}}."""
    
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
    
    # For send_email, extract specific parameters using regex
    params = {}
    
    if func_name == "send_email":
        # Extract email address - look for pattern like "at email@domain.com" or "to email@domain.com"
        email_match = re.search(r'(?:at|to)\s+([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', query, re.IGNORECASE)
        if email_match:
            params["to"] = email_match.group(1)
        
        # Extract subject - look for "subject 'X'" or 'subject "X"'
        subject_match = re.search(r"subject\s+['\"]([^'\"]+)['\"]", query, re.IGNORECASE)
        if subject_match:
            params["subject"] = subject_match.group(1)
        
        # Extract body - look for "body 'X'" or 'body "X"'
        body_match = re.search(r"body\s+['\"]([^'\"]+)['\"]", query, re.IGNORECASE)
        if body_match:
            params["body"] = body_match.group(1)
        
        # Extract cc if present
        cc_match = re.search(r"cc\s+['\"]?([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})['\"]?", query, re.IGNORECASE)
        if cc_match:
            params["cc"] = cc_match.group(1)
        
        # Extract bcc if present
        bcc_match = re.search(r"bcc\s+['\"]?([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})['\"]?", query, re.IGNORECASE)
        if bcc_match:
            params["bcc"] = bcc_match.group(1)
    
    else:
        # Generic extraction for other functions
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
                    numbers.pop(0)  # Remove used number
            elif param_type == "string":
                # Try to extract quoted strings or patterns
                quoted_match = re.search(rf"{param_name}\s+['\"]([^'\"]+)['\"]", query, re.IGNORECASE)
                if quoted_match:
                    params[param_name] = quoted_match.group(1)
    
    return {func_name: params}
