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
    
    # Parse functions (may be JSON string)
    try:
        if isinstance(functions, str):
            funcs = json.loads(functions)
        else:
            funcs = functions
    except (json.JSONDecodeError, TypeError):
        funcs = []
    
    if not funcs:
        return {"error": "No functions provided"}
    
    func = funcs[0]
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters from query using regex and string matching
    params = {}
    query_lower = query.lower()
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        enum_values = param_info.get("enum", [])
        
        # Handle enum parameters (like genre)
        if enum_values:
            for enum_val in enum_values:
                if enum_val.lower() in query_lower:
                    params[param_name] = enum_val
                    break
        
        # Handle location parameter
        elif "location" in param_name or "city" in param_desc:
            # Common patterns: "in <city>", "at <city>", "for <city>"
            location_patterns = [
                r'in\s+([A-Z][a-zA-Z\s]+?)(?:\s+for|\s+next|\s+this|\.|\,|$)',
                r'at\s+([A-Z][a-zA-Z\s]+?)(?:\s+for|\s+next|\s+this|\.|\,|$)',
                r'concerts?\s+in\s+([A-Z][a-zA-Z\s]+?)(?:\s+for|\s+next|\s+this|\.|\,|$)',
            ]
            for pattern in location_patterns:
                match = re.search(pattern, query)
                if match:
                    params[param_name] = match.group(1).strip()
                    break
        
        # Handle date/time parameter
        elif "date" in param_name or "time" in param_desc:
            # Common patterns: "next month", "this week", "tomorrow", specific dates
            date_patterns = [
                r'(next\s+(?:month|week|year|weekend))',
                r'(this\s+(?:month|week|year|weekend))',
                r'(tomorrow|today)',
                r'for\s+(next\s+\w+)',
                r'on\s+(\w+\s+\d+(?:st|nd|rd|th)?(?:\s*,?\s*\d{4})?)',
                r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
            ]
            for pattern in date_patterns:
                match = re.search(pattern, query_lower)
                if match:
                    params[param_name] = match.group(1).strip()
                    break
    
    return {func_name: params}
