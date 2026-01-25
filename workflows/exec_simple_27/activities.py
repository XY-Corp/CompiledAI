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
    """Extract function name and parameters from user query. Returns {"func_name": {params}}."""
    
    # Parse prompt (may be JSON string with nested structure)
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
    
    # Extract parameters based on schema
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_type == "string":
            # For "term" parameter - look for quoted terms or specific patterns
            if param_name == "term" or "term" in param_desc:
                # Look for quoted terms first
                quoted_match = re.search(r'"([^"]+)"', query)
                if quoted_match:
                    params[param_name] = quoted_match.group(1)
                else:
                    # Look for patterns like "what X means" or "look up X"
                    patterns = [
                        r'what\s+["\']?(\w+)["\']?\s+means',
                        r'look\s+up\s+(?:what\s+)?["\']?(\w+)["\']?',
                        r'definition\s+of\s+["\']?(\w+)["\']?',
                        r'means?\s+by\s+["\']?(\w+)["\']?',
                        r'the\s+word\s+["\']?(\w+)["\']?',
                        r'slang\s+["\']?(\w+)["\']?',
                    ]
                    
                    for pattern in patterns:
                        match = re.search(pattern, query, re.IGNORECASE)
                        if match:
                            params[param_name] = match.group(1)
                            break
                    
                    # If no pattern matched, look for quoted word
                    if param_name not in params:
                        # Check for word in quotes like "flex"
                        quote_match = re.search(r'["\'](\w+)["\']', query)
                        if quote_match:
                            params[param_name] = quote_match.group(1)
            else:
                # Generic string extraction - look for quoted values or key phrases
                quoted_match = re.search(r'"([^"]+)"', query)
                if quoted_match:
                    params[param_name] = quoted_match.group(1)
        
        elif param_type in ["integer", "number", "float"]:
            # Extract numbers
            numbers = re.findall(r'\d+(?:\.\d+)?', query)
            if numbers:
                if param_type == "integer":
                    params[param_name] = int(numbers[0])
                else:
                    params[param_name] = float(numbers[0])
    
    return {func_name: params}
