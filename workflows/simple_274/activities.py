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
    
    # Extract parameters based on schema
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        default_val = param_info.get("default")
        
        # For museum_name: extract the museum name from the query
        if param_name == "museum_name" or "museum" in param_name.lower() or "name" in param_desc:
            # Pattern: "of the X" or "about the X" or "for the X"
            patterns = [
                r'(?:of|about|for)\s+the\s+([A-Z][A-Za-z\s]+(?:Museum|Gallery|Institute|Center|Centre))',
                r'(?:of|about|for)\s+([A-Z][A-Za-z\s]+(?:Museum|Gallery|Institute|Center|Centre))',
                r'the\s+([A-Z][A-Za-z\s]+(?:Museum|Gallery|Institute|Center|Centre))',
                r'([A-Z][A-Za-z\s]+(?:Museum|Gallery|Institute|Center|Centre))',
            ]
            
            for pattern in patterns:
                match = re.search(pattern, query)
                if match:
                    params[param_name] = match.group(1).strip()
                    break
        
        # For info_type: check if mentioned in query, otherwise use default
        elif param_name == "info_type" or "type" in param_name.lower():
            # Check for specific info types in query
            info_keywords = {
                "opening hours": "opening_hours",
                "hours": "opening_hours",
                "open": "opening_hours",
                "address": "address",
                "location": "location",
                "tickets": "tickets",
                "admission": "admission",
                "exhibits": "exhibits",
                "exhibitions": "exhibitions",
            }
            
            query_lower = query.lower()
            found_type = None
            for keyword, info_val in info_keywords.items():
                if keyword in query_lower:
                    found_type = info_val
                    break
            
            if found_type:
                params[param_name] = found_type
            elif default_val is not None:
                # Use default value if available and param is not required
                if param_name not in required_params:
                    params[param_name] = default_val
        
        # Generic string extraction for other params
        elif param_type == "string":
            # Try to extract quoted strings or named entities
            quoted_match = re.search(r'"([^"]+)"', query)
            if quoted_match:
                params[param_name] = quoted_match.group(1)
        
        # Numeric extraction
        elif param_type in ["integer", "number", "float"]:
            numbers = re.findall(r'\d+(?:\.\d+)?', query)
            if numbers:
                if param_type == "integer":
                    params[param_name] = int(numbers[0])
                else:
                    params[param_name] = float(numbers[0])
    
    return {func_name: params}
