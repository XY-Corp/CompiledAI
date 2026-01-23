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
    """Extract function call parameters from user query using regex and string matching."""
    
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
        param_desc = param_info.get("description", "").lower()
        
        if param_type == "integer":
            # Extract year - look for 4-digit numbers (years)
            if "year" in param_name.lower() or "year" in param_desc:
                year_match = re.search(r'\b(19\d{2}|20\d{2})\b', query)
                if year_match:
                    params[param_name] = int(year_match.group(1))
            else:
                # Generic integer extraction
                numbers = re.findall(r'\b\d+\b', query)
                if numbers:
                    params[param_name] = int(numbers[0])
        
        elif param_type == "string":
            if "company" in param_name.lower() or "company" in param_desc:
                # Extract company name - look for quoted names or patterns like "company 'X'" or "company X"
                # Try quoted patterns first
                quoted_match = re.search(r"['\"]([^'\"]+)['\"]", query)
                if quoted_match:
                    params[param_name] = quoted_match.group(1)
                else:
                    # Try "company X" pattern
                    company_match = re.search(r'company\s+([A-Z][A-Za-z\s\.]+?)(?:\s+from|\s+in|\s+during|$)', query, re.IGNORECASE)
                    if company_match:
                        params[param_name] = company_match.group(1).strip()
            
            elif "type" in param_name.lower() or "case_type" in param_name.lower():
                # Extract case type - look for keywords like patent, commercial, IPR
                case_types = ["patent", "commercial", "ipr", "civil", "criminal", "trademark", "copyright"]
                query_lower = query.lower()
                for case_type in case_types:
                    if case_type in query_lower:
                        # Capitalize properly
                        params[param_name] = case_type.upper() if case_type == "ipr" else case_type.capitalize()
                        break
    
    return {func_name: params}
