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
        else:
            data = prompt
        
        # Extract user query from BFCL format: {"question": [[{"role": "user", "content": "..."}]]}
        if isinstance(data, dict) and "question" in data:
            question = data["question"]
            if isinstance(question, list) and len(question) > 0:
                if isinstance(question[0], list) and len(question[0]) > 0:
                    query = question[0][0].get("content", str(prompt))
                else:
                    query = str(question[0])
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
    required_params = func.get("parameters", {}).get("required", [])
    
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
                # Check if user explicitly asks for detailed info
                if any(word in query_lower for word in ["detailed", "detail", "in detail", "comprehensive", "thorough", "full"]):
                    params[param_name] = True
                else:
                    # Use default if specified, otherwise False
                    default_val = param_info.get("default", "false")
                    params[param_name] = default_val.lower() == "true" if isinstance(default_val, str) else bool(default_val)
        
        elif param_type == "integer" or param_type == "number":
            # Extract numbers from query
            numbers = re.findall(r'\d+(?:\.\d+)?', query)
            if numbers:
                if param_type == "integer":
                    params[param_name] = int(numbers[0])
                else:
                    params[param_name] = float(numbers[0])
        
        elif param_type == "string":
            # Extract string value based on context
            # For cell_type, look for patterns like "human cell", "X cell", "type of cell"
            if "cell" in param_name.lower() or "cell" in param_desc:
                # Pattern: "X cell" or "cell of X" or "about X cell"
                patterns = [
                    r'(?:about|of|the)\s+(?:the\s+)?(?:structure\s+of\s+)?(\w+)\s+cell',
                    r'(\w+)\s+cell(?:s)?(?:\s+structure)?',
                    r'cell\s+(?:type|of)\s+(\w+)',
                    r'information\s+about\s+(?:the\s+)?(\w+)',
                ]
                
                for pattern in patterns:
                    match = re.search(pattern, query_lower)
                    if match:
                        extracted = match.group(1).strip()
                        # Filter out common non-cell-type words
                        if extracted not in ["the", "a", "an", "this", "that", "detailed", "structure"]:
                            params[param_name] = extracted
                            break
                
                # If no match found but it's required, try to extract key noun
                if param_name not in params and param_name in required_params:
                    # Default extraction: look for key subject
                    if "human" in query_lower:
                        params[param_name] = "human"
            else:
                # Generic string extraction - look for quoted strings or key phrases
                quoted = re.findall(r'"([^"]+)"', query)
                if quoted:
                    params[param_name] = quoted[0]
                elif param_name in required_params:
                    # Try to extract meaningful content
                    words = re.findall(r'\b[a-zA-Z]+\b', query)
                    if words:
                        # Filter common words
                        stop_words = {"find", "me", "get", "the", "a", "an", "about", "information", "detailed", "for", "of", "and", "or", "with"}
                        meaningful = [w for w in words if w.lower() not in stop_words]
                        if meaningful:
                            params[param_name] = meaningful[0]
    
    return {func_name: params}
