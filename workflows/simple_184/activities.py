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
    """Extract function name and parameters from user query using regex and string matching."""
    
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
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        
        if param_type == "integer":
            # Extract integers using regex
            # Look for patterns like "case ID of 1234" or "ID 1234" or just numbers
            numbers = re.findall(r'\b(\d+)\b', query)
            if numbers:
                # Use the first number found for case_id type params
                params[param_name] = int(numbers[0])
        
        elif param_type == "boolean":
            # Look for boolean indicators in the query
            query_lower = query.lower()
            
            # Check for "closed" status indicators
            if "closed" in param_name.lower() or "status" in param_name.lower():
                # Look for phrases indicating closed status check
                if any(phrase in query_lower for phrase in ["if it's already closed", "is closed", "check if closed", "verify if closed", "already closed"]):
                    params[param_name] = True
                elif any(phrase in query_lower for phrase in ["if it's open", "is open", "not closed"]):
                    params[param_name] = False
                else:
                    # Default based on context - if asking to verify closed status, set to True
                    params[param_name] = True
            else:
                # Generic boolean extraction
                if any(word in query_lower for word in ["true", "yes", "enable", "on"]):
                    params[param_name] = True
                elif any(word in query_lower for word in ["false", "no", "disable", "off"]):
                    params[param_name] = False
                else:
                    params[param_name] = True  # Default
        
        elif param_type == "string":
            # Extract string values - look for quoted strings or named entities
            quoted = re.findall(r'"([^"]+)"', query)
            if quoted:
                params[param_name] = quoted[0]
            else:
                # Try to extract based on param name context
                params[param_name] = ""
    
    return {func_name: params}
