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
    
    # Parse prompt - may be JSON string with nested structure
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
        else:
            data = prompt
        
        # Extract user query from BFCL format: {"question": [[{"role": "user", "content": "..."}]]}
        if isinstance(data, dict) and "question" in data:
            question_data = data.get("question", [])
            if isinstance(question_data, list) and len(question_data) > 0:
                first_item = question_data[0]
                if isinstance(first_item, list) and len(first_item) > 0:
                    query = first_item[0].get("content", str(prompt))
                elif isinstance(first_item, dict):
                    query = first_item.get("content", str(prompt))
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
    
    if not funcs:
        return {"error": "No functions provided"}
    
    # Get function details
    func = funcs[0] if isinstance(funcs, list) else funcs
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters from query using regex and string matching
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        # Location extraction patterns
        if "location" in param_name.lower() or "location" in param_desc:
            # Pattern: "in [Location]" or "for [Location]" or "at [Location]"
            location_patterns = [
                r'(?:in|for|at)\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)',  # "in San Diego"
                r'(?:in|for|at)\s+([A-Za-z\s]+?)(?:\s+(?:at|on|during|for|$))',  # More flexible
            ]
            
            for pattern in location_patterns:
                match = re.search(pattern, query)
                if match:
                    location = match.group(1).strip()
                    # Clean up trailing words that aren't part of location
                    location = re.sub(r'\s+(at|on|during|for|the|a|an)$', '', location, flags=re.IGNORECASE)
                    if location:
                        params[param_name] = location
                        break
        
        # Time extraction patterns
        elif "time" in param_name.lower() or "time" in param_desc:
            # Pattern: "at [time]" or specific time formats
            time_patterns = [
                r'at\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm|AM|PM)?)',  # "at 12pm" or "at 12:00pm"
                r'(\d{1,2}(?::\d{2})?\s*(?:am|pm|AM|PM))',  # Just "12pm"
                r'at\s+(\d{1,2}\s*(?:o\'?clock)?)',  # "at 12 o'clock"
                r'(morning|afternoon|evening|night|noon|midnight)',  # Time of day
            ]
            
            for pattern in time_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    params[param_name] = match.group(1).strip()
                    break
        
        # Generic number extraction for numeric types
        elif param_type in ["integer", "number", "float"]:
            numbers = re.findall(r'\d+(?:\.\d+)?', query)
            if numbers:
                if param_type == "integer":
                    params[param_name] = int(float(numbers[0]))
                else:
                    params[param_name] = float(numbers[0])
        
        # Generic string extraction - try to find quoted strings or key phrases
        elif param_type == "string":
            # Try quoted strings first
            quoted = re.findall(r'"([^"]+)"', query)
            if quoted:
                params[param_name] = quoted[0]
    
    return {func_name: params}
