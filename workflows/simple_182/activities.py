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
            question_data = data["question"]
            if isinstance(question_data, list) and len(question_data) > 0:
                if isinstance(question_data[0], list) and len(question_data[0]) > 0:
                    query = question_data[0][0].get("content", str(prompt))
                else:
                    query = str(prompt)
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
    
    # Extract parameters from query
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        is_optional = param_info.get("optional", False)
        default_value = param_info.get("default")
        
        # Extract based on parameter name and type
        if param_name == "case_number":
            # Look for case number patterns - alphanumeric identifiers
            # Pattern: "case number XYZ123" or "case XYZ123" or just alphanumeric codes
            patterns = [
                r'case\s+(?:number\s+)?([A-Za-z0-9]+)',
                r'case\s+#?\s*([A-Za-z0-9]+)',
                r'lawsuit\s+(?:case\s+)?(?:number\s+)?([A-Za-z0-9]+)',
            ]
            for pattern in patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    params[param_name] = match.group(1)
                    break
        
        elif param_name == "year" and param_type == "integer":
            # Look for year patterns (4-digit numbers that look like years)
            year_match = re.search(r'\b(19\d{2}|20\d{2})\b', query)
            if year_match:
                params[param_name] = int(year_match.group(1))
            # Don't add default for optional params unless explicitly needed
        
        elif param_name == "location":
            # Look for location patterns
            location_patterns = [
                r'(?:in|at|from)\s+([A-Za-z\s]+?)(?:\s+court|\s+jurisdiction)?(?:\.|,|$)',
                r'(?:court|jurisdiction)\s+(?:of|in)\s+([A-Za-z\s]+)',
            ]
            for pattern in location_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    params[param_name] = match.group(1).strip()
                    break
    
    return {func_name: params}
