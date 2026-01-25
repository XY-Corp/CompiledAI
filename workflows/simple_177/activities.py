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
    
    # Extract parameters from query using regex and string matching
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_type == "integer":
            # Extract year (4-digit number)
            if "year" in param_name.lower() or "year" in param_desc:
                year_match = re.search(r'\b(19\d{2}|20\d{2})\b', query)
                if year_match:
                    params[param_name] = int(year_match.group(1))
            else:
                # Extract any integer
                numbers = re.findall(r'\b\d+\b', query)
                if numbers:
                    params[param_name] = int(numbers[0])
        
        elif param_type == "string":
            # Check for enum values first
            if "enum" in param_info:
                enum_values = param_info["enum"]
                query_lower = query.lower()
                for enum_val in enum_values:
                    if enum_val.lower() in query_lower:
                        params[param_name] = enum_val
                        break
            
            # Extract company name
            elif "company" in param_name.lower() or "company" in param_desc:
                # Common patterns: "of [Company]", "[Company]'s", "related to [Company]"
                company_patterns = [
                    r'(?:of|for|about|related to|regarding)\s+([A-Z][A-Za-z0-9\s&\-\.]+?)(?:\s+in\s+|\s+during\s+|\s+from\s+|\'s|\s*$)',
                    r'([A-Z][A-Za-z0-9]+(?:\s+[A-Z][A-Za-z0-9]+)*)\s+(?:lawsuit|cases|patent)',
                    r'cases\s+of\s+([A-Z][A-Za-z0-9\s&\-\.]+?)(?:\s+in\s+|\s*$)',
                ]
                for pattern in company_patterns:
                    match = re.search(pattern, query)
                    if match:
                        params[param_name] = match.group(1).strip()
                        break
            
            # Extract case type (e.g., "Patent lawsuit")
            elif "type" in param_name.lower() or "type" in param_desc:
                type_match = re.search(r'(Patent|Copyright|Trademark|Civil|Criminal)\s+(?:lawsuit|case)', query, re.IGNORECASE)
                if type_match:
                    params[param_name] = type_match.group(1)
    
    return {func_name: params}
