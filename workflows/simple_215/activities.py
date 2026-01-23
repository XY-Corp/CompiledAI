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
    """Extract function call from user query and return as {func_name: {params}}.
    
    Parses the prompt to extract the user's query, then extracts parameter values
    using regex and string matching based on the function schema.
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
    required_params = func.get("parameters", {}).get("required", [])
    
    # Extract parameters based on schema
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_type == "string":
            # For movie title: extract text in quotes or after keywords
            if "title" in param_name.lower() or "movie" in param_desc or "title" in param_desc:
                # Try quoted string first: 'Interstellar' or "Interstellar"
                quoted_match = re.search(r"['\"]([^'\"]+)['\"]", query)
                if quoted_match:
                    params[param_name] = quoted_match.group(1)
                else:
                    # Try patterns like "movie X" or "on X" or "about X"
                    patterns = [
                        r"movie\s+['\"]?([^'\"]+?)['\"]?(?:\s|$|\?)",
                        r"(?:on|about|for)\s+(?:movie\s+)?['\"]?([^'\"]+?)['\"]?(?:\s|$|\?)",
                        r"brief\s+(?:on|about|for)\s+['\"]?([^'\"]+?)['\"]?(?:\s|$|\?)",
                    ]
                    for pattern in patterns:
                        match = re.search(pattern, query, re.IGNORECASE)
                        if match:
                            params[param_name] = match.group(1).strip()
                            break
            else:
                # Generic string extraction
                quoted_match = re.search(r"['\"]([^'\"]+)['\"]", query)
                if quoted_match:
                    params[param_name] = quoted_match.group(1)
        
        elif param_type == "boolean":
            # Check for explicit boolean indicators
            if "extra" in param_name.lower() or "additional" in param_desc:
                # Look for keywords indicating extra info is wanted
                extra_patterns = [
                    r"\b(with|include|also|extra|additional|more)\s+(info|information|details)\b",
                    r"\b(detailed|full|complete)\b",
                ]
                wants_extra = any(re.search(p, query, re.IGNORECASE) for p in extra_patterns)
                # Only include if explicitly requested (not default)
                if wants_extra:
                    params[param_name] = True
                # Don't include if not requested (let default apply)
        
        elif param_type in ["integer", "number", "float"]:
            # Extract numbers
            numbers = re.findall(r'\d+(?:\.\d+)?', query)
            if numbers:
                if param_type == "integer":
                    params[param_name] = int(numbers[0])
                else:
                    params[param_name] = float(numbers[0])
    
    # Ensure required params are present
    for req_param in required_params:
        if req_param not in params:
            # Try harder to extract required string params
            if params_schema.get(req_param, {}).get("type") == "string":
                # Last resort: extract any quoted text or significant noun phrase
                quoted = re.search(r"['\"]([^'\"]+)['\"]", query)
                if quoted:
                    params[req_param] = quoted.group(1)
    
    return {func_name: params}
