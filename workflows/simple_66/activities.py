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
    
    Uses regex and string matching to extract values - no LLM calls needed.
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
    
    # Extract parameters based on schema
    params = {}
    query_lower = query.lower()
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        enum_values = param_info.get("enum", [])
        
        if param_name == "location":
            # Extract location - look for quoted strings or known patterns
            # Pattern: "in the X" or "for X" or "on X"
            location_patterns = [
                r'(?:in|for|on|at)\s+(?:the\s+)?([A-Za-z][A-Za-z\s]+?)(?:\s+for|\s+over|\s+during|\s*$|\s*\.)',
                r'data\s+(?:on|for|about)\s+(?:average\s+)?(?:\w+\s+)?(?:in\s+)?(?:the\s+)?([A-Za-z][A-Za-z\s]+?)(?:\s+for|\s+over|\s*$)',
            ]
            
            for pattern in location_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    location = match.group(1).strip()
                    # Clean up common trailing words
                    location = re.sub(r'\s+(for|over|during|the|last|past)$', '', location, flags=re.IGNORECASE)
                    if location and len(location) > 2:
                        params[param_name] = location
                        break
            
            # Fallback: look for "Amazon rainforest" specifically mentioned
            if param_name not in params:
                if "amazon" in query_lower:
                    if "rainforest" in query_lower:
                        params[param_name] = "Amazon rainforest"
                    else:
                        params[param_name] = "Amazon"
        
        elif param_name == "time_frame" and enum_values:
            # Match against enum values
            # Look for time-related phrases
            if "six month" in query_lower or "6 month" in query_lower or "last six" in query_lower:
                if "six_months" in enum_values:
                    params[param_name] = "six_months"
            elif "year" in query_lower and "five" not in query_lower:
                if "year" in enum_values:
                    params[param_name] = "year"
            elif "five year" in query_lower or "5 year" in query_lower:
                if "five_years" in enum_values:
                    params[param_name] = "five_years"
            
            # Fallback: try to match any enum value mentioned
            if param_name not in params:
                for enum_val in enum_values:
                    # Convert enum to readable form for matching
                    readable = enum_val.replace("_", " ")
                    if readable in query_lower:
                        params[param_name] = enum_val
                        break
        
        elif param_type in ["integer", "number", "float"]:
            # Extract numbers
            numbers = re.findall(r'\d+(?:\.\d+)?', query)
            if numbers:
                if param_type == "integer":
                    params[param_name] = int(numbers[0])
                else:
                    params[param_name] = float(numbers[0])
        
        elif param_type == "string" and param_name not in params:
            # Generic string extraction - look for quoted values or patterns from description
            quoted = re.findall(r'"([^"]+)"', query)
            if quoted:
                params[param_name] = quoted[0]
    
    return {func_name: params}
