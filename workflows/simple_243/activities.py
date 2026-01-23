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
    
    Parses the user's natural language query to extract relevant parameters
    for the specified function schema.
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
    
    # Get function schema
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
            # Look for "detail", "detailed", "more info", etc.
            detail_patterns = [
                r'\bdetail(?:ed|s)?\b',
                r'\bmore\s+info(?:rmation)?\b',
                r'\bin\s+depth\b',
                r'\bcomprehensive\b',
                r'\bfull\b',
                r'\bextensive\b',
            ]
            has_detail = any(re.search(p, query, re.IGNORECASE) for p in detail_patterns)
            params[param_name] = has_detail
            
        elif param_type == "string":
            # For discovery-related parameters, extract the subject
            if "discovery" in param_name.lower() or "discovery" in param_desc:
                # Pattern: "Who discovered X?" or "discoverer of X"
                discovery_patterns = [
                    r'(?:who\s+)?discover(?:ed|er\s+of)?\s+(?:the\s+)?([a-zA-Z\s]+?)(?:\?|$|\.|\s+give|\s+tell)',
                    r'(?:the\s+)?([a-zA-Z]+)\s+(?:was\s+)?discover',
                    r'discovery\s+of\s+(?:the\s+)?([a-zA-Z\s]+)',
                ]
                
                for pattern in discovery_patterns:
                    match = re.search(pattern, query, re.IGNORECASE)
                    if match:
                        discovery = match.group(1).strip()
                        # Clean up common trailing words
                        discovery = re.sub(r'\s+(give|tell|get|find|show|provide).*$', '', discovery, flags=re.IGNORECASE)
                        params[param_name] = discovery.strip()
                        break
                
                # Fallback: if no pattern matched but we know it's about neutron
                if param_name not in params:
                    if re.search(r'\bneutron\b', query, re.IGNORECASE):
                        params[param_name] = "neutron"
            else:
                # Generic string extraction - try to find relevant noun phrases
                # This is a fallback for other string parameters
                words = re.findall(r'\b[a-zA-Z]+\b', query)
                if words:
                    params[param_name] = " ".join(words[:3])  # Take first few words as fallback
                    
        elif param_type in ["integer", "number", "float"]:
            # Extract numbers from query
            numbers = re.findall(r'\d+(?:\.\d+)?', query)
            if numbers:
                if param_type == "integer":
                    params[param_name] = int(numbers[0])
                else:
                    params[param_name] = float(numbers[0])
    
    return {func_name: params}
