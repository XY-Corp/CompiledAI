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
        
        # Strategy 1: Look for ID patterns (e.g., DNA123, ID_456, etc.)
        if "id" in param_name.lower() or "id" in param_desc:
            # Match various ID patterns: DNA123, DNA_123, dna-123, etc.
            id_patterns = [
                r'id\s*[`\'"]?([A-Za-z0-9_-]+)[`\'"]?',  # id `DNA123` or id DNA123
                r'[`\'"]([A-Za-z]+\d+)[`\'"]',  # `DNA123` in backticks/quotes
                r'\b([A-Z]+\d+)\b',  # DNA123 pattern (letters followed by numbers)
            ]
            
            for pattern in id_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    params[param_name] = match.group(1)
                    break
        
        # Strategy 2: Extract integers
        elif param_type == "integer":
            # Look for numbers in context of the parameter
            numbers = re.findall(r'\b(\d+)\b', query)
            if numbers:
                # Use the first number found (could be smarter based on context)
                params[param_name] = int(numbers[0])
        
        # Strategy 3: Extract format strings
        elif "format" in param_name.lower():
            # Look for format specifications
            format_match = re.search(r'format\s*[=:]\s*[\'"]?(\w+)[\'"]?', query, re.IGNORECASE)
            if format_match:
                params[param_name] = format_match.group(1)
            # Also check for common format names mentioned
            elif re.search(r'\b(fasta|json|xml|csv|genbank)\b', query, re.IGNORECASE):
                format_match = re.search(r'\b(fasta|json|xml|csv|genbank)\b', query, re.IGNORECASE)
                params[param_name] = format_match.group(1).lower()
    
    # Only include required params and params we actually found values for
    # Filter out empty/None values for optional params
    final_params = {}
    for param_name in params_schema.keys():
        if param_name in params and params[param_name] is not None:
            final_params[param_name] = params[param_name]
        elif param_name in required_params:
            # For required params we couldn't extract, include with best guess
            if param_name in params:
                final_params[param_name] = params[param_name]
    
    return {func_name: final_params}
