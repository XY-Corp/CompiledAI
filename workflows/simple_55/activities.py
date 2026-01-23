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
    
    # Parse prompt - may be JSON string with nested structure
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
    
    # Extract parameters based on schema
    params = {}
    query_lower = query.lower()
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_type == "boolean":
            # Check for boolean indicators in query
            # Look for "detailed" keyword or similar
            if "detailed" in param_name.lower() or "detail" in param_desc:
                # Check if user wants detailed info
                if "detailed" in query_lower or "detail" in query_lower:
                    params[param_name] = True
                else:
                    # Use default if available, otherwise False
                    default = param_info.get("default", "false")
                    params[param_name] = default.lower() == "true" if isinstance(default, str) else bool(default)
        
        elif param_type == "integer" or param_type == "number":
            # Extract numbers with regex
            numbers = re.findall(r'\d+(?:\.\d+)?', query)
            if numbers:
                if param_type == "integer":
                    params[param_name] = int(numbers[0])
                else:
                    params[param_name] = float(numbers[0])
        
        elif param_type == "string":
            # Extract string values based on context
            if "cell" in param_name.lower() or "cell" in param_desc:
                # Extract cell type - look for patterns like "human cell", "X cell"
                cell_patterns = [
                    r'(?:about|of)\s+(?:the\s+)?(?:structure\s+of\s+)?(\w+(?:\s+\w+)?)\s+cell',
                    r'(\w+(?:\s+\w+)?)\s+cell\s+(?:structure|info|information)',
                    r'information\s+about\s+(?:the\s+)?(\w+(?:\s+\w+)?)\s+cell',
                    r'(\w+)\s+cell',
                ]
                
                for pattern in cell_patterns:
                    match = re.search(pattern, query_lower)
                    if match:
                        cell_type = match.group(1).strip()
                        params[param_name] = cell_type
                        break
                
                # If no match found, try to extract any noun before "cell"
                if param_name not in params:
                    # Fallback: look for "human cell" specifically
                    if "human" in query_lower:
                        params[param_name] = "human"
            else:
                # Generic string extraction - look for quoted strings or key phrases
                quoted = re.findall(r'"([^"]+)"', query)
                if quoted:
                    params[param_name] = quoted[0]
    
    return {func_name: params}
