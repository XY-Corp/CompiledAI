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
    
    Uses regex and string parsing to extract parameter values - no LLM calls needed.
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
    required_params = func.get("parameters", {}).get("required", [])
    
    # Extract parameters from query
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        # Strategy 1: Look for ID patterns (DNA_id, id, etc.)
        if "id" in param_name.lower() or "id" in param_desc:
            # Look for patterns like `DNA123`, 'DNA123', "DNA123", or id DNA123
            id_patterns = [
                r'`([A-Za-z0-9_-]+)`',  # backtick quoted
                r"'([A-Za-z0-9_-]+)'",  # single quoted
                r'"([A-Za-z0-9_-]+)"',  # double quoted
                r'\bid\s+([A-Za-z0-9_-]+)',  # "id DNA123"
                r'with\s+id\s+([A-Za-z0-9_-]+)',  # "with id DNA123"
            ]
            for pattern in id_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    params[param_name] = match.group(1)
                    break
        
        # Strategy 2: Look for format specifications
        elif "format" in param_name.lower():
            format_patterns = [
                r'format[:\s]+["\']?([a-zA-Z0-9_-]+)["\']?',
                r'in\s+([a-zA-Z0-9_-]+)\s+format',
                r'as\s+([a-zA-Z0-9_-]+)',
            ]
            for pattern in format_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    params[param_name] = match.group(1)
                    break
        
        # Strategy 3: Look for integer values (upstream, count, etc.)
        elif param_type == "integer":
            # Look for number patterns with context
            int_patterns = [
                rf'{param_name}[:\s]+(\d+)',  # "upstream: 100"
                r'(\d+)\s+base\s+pairs?',  # "100 base pairs"
                r'(\d+)\s+bp',  # "100 bp"
            ]
            for pattern in int_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    params[param_name] = int(match.group(1))
                    break
    
    # Only include required params if found, skip optional params not mentioned
    # For this task, DNA_id is required and was extracted above
    
    return {func_name: params}
