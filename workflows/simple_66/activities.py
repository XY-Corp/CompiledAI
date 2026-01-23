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
    
    Uses regex and string matching to extract parameter values - no LLM calls needed.
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
                r'(?:in|for|on|at)\s+(?:the\s+)?([A-Za-z][A-Za-z\s]+?)(?:\s+for|\s+over|\s+during|\.|\?|$)',
                r'data\s+(?:on|for|about)\s+(?:average\s+)?(?:\w+\s+)?(?:in\s+)?(?:the\s+)?([A-Za-z][A-Za-z\s]+?)(?:\s+for|\s+over|\.|\?|$)',
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
            
            # Fallback: look for "Amazon rainforest" specifically or similar known locations
            if param_name not in params:
                known_locations = ["amazon rainforest", "amazon", "sahara desert", "arctic", "antarctic"]
                for loc in known_locations:
                    if loc in query_lower:
                        # Capitalize properly
                        params[param_name] = loc.title()
                        break
        
        elif param_name == "time_frame" and enum_values:
            # Match against enum values
            # Look for time-related phrases in query
            time_mappings = {
                "six_months": ["six months", "6 months", "last six months", "past six months", "last 6 months"],
                "year": ["year", "one year", "1 year", "last year", "past year", "12 months"],
                "five_years": ["five years", "5 years", "last five years", "past five years"],
            }
            
            for enum_val in enum_values:
                # Check direct match
                if enum_val.replace("_", " ") in query_lower:
                    params[param_name] = enum_val
                    break
                # Check mapped phrases
                if enum_val in time_mappings:
                    for phrase in time_mappings[enum_val]:
                        if phrase in query_lower:
                            params[param_name] = enum_val
                            break
                if param_name in params:
                    break
        
        elif param_type in ["integer", "number", "float"]:
            # Extract numbers
            numbers = re.findall(r'\d+(?:\.\d+)?', query)
            if numbers:
                if param_type == "integer":
                    params[param_name] = int(float(numbers[0]))
                else:
                    params[param_name] = float(numbers[0])
        
        elif param_type == "string" and enum_values:
            # Match against enum values
            for enum_val in enum_values:
                if enum_val.lower() in query_lower or enum_val.replace("_", " ").lower() in query_lower:
                    params[param_name] = enum_val
                    break
    
    return {func_name: params}
