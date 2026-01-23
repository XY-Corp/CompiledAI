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
    """Extract function call parameters from user query and return as {func_name: {params}}.
    
    Parses the user's natural language query to extract the appropriate function
    and its parameters based on the available function schemas.
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
    
    # Extract parameters based on schema
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_type == "boolean":
            # Check for boolean indicators in query
            # Look for keywords indicating true: "detailed", "detail", "full", "complete", etc.
            detail_keywords = ["detail", "detailed", "full", "complete", "comprehensive", "all"]
            has_detail_request = any(kw in query.lower() for kw in detail_keywords)
            params[param_name] = has_detail_request
        
        elif param_type == "string":
            # Extract string values - look for quoted strings or case names
            # Pattern for case names like 'R vs Adams' or "R vs Adams"
            quoted_match = re.search(r"['\"]([^'\"]+)['\"]", query)
            if quoted_match:
                params[param_name] = quoted_match.group(1)
            else:
                # Try to extract case name pattern (X vs Y, X v Y, X v. Y)
                case_match = re.search(r"(\w+\s+(?:vs?\.?|versus)\s+\w+)", query, re.IGNORECASE)
                if case_match:
                    params[param_name] = case_match.group(1)
                else:
                    # Fallback: extract any identifier-like string
                    params[param_name] = "<UNKNOWN>"
        
        elif param_type in ["integer", "number", "float"]:
            # Extract numbers
            numbers = re.findall(r'\d+(?:\.\d+)?', query)
            if numbers:
                if param_type == "integer":
                    params[param_name] = int(numbers[0])
                else:
                    params[param_name] = float(numbers[0])
    
    return {func_name: params}
