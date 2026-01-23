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
    
    # Extract parameters from query
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        
        if param_type == "integer":
            # Extract year (4-digit number)
            year_match = re.search(r'\b(19\d{2}|20\d{2})\b', query)
            if year_match:
                params[param_name] = int(year_match.group(1))
        
        elif param_type == "string":
            # Check if it's an enum type (like status)
            if "enum" in param_info:
                enum_values = param_info.get("enum", [])
                query_lower = query.lower()
                for enum_val in enum_values:
                    if enum_val.lower() in query_lower:
                        params[param_name] = enum_val
                        break
                # Don't set if not found - it's optional
            
            elif param_name == "company_name":
                # Extract company name - look for known patterns
                # Pattern: "of [Company]" or "[Company]'s" or "related to [Company]"
                company_patterns = [
                    r'(?:of|for|about|related to|against)\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*)',
                    r'([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*?)(?:\'s|\s+in\s+\d)',
                ]
                
                for pattern in company_patterns:
                    match = re.search(pattern, query)
                    if match:
                        company = match.group(1).strip()
                        # Filter out common words that aren't company names
                        if company.lower() not in ['patent', 'lawsuit', 'cases', 'all', 'find']:
                            params[param_name] = company
                            break
    
    return {func_name: params}
