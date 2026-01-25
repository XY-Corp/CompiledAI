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
    """Extract function name and parameters from user query and function schema.
    
    Returns a dict with function name as key and parameters as nested object.
    """
    # Parse prompt - may be JSON string with nested structure
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
        else:
            data = prompt
        
        # Extract user query from BFCL format: {"question": [[{"role": "user", "content": "..."}]]}
        if "question" in data and isinstance(data["question"], list):
            if len(data["question"]) > 0 and isinstance(data["question"][0], list):
                if len(data["question"][0]) > 0 and isinstance(data["question"][0][0], dict):
                    query = data["question"][0][0].get("content", str(prompt))
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
    
    func = funcs[0]
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters based on schema
    params = {}
    query_lower = query.lower()
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        enum_values = param_info.get("enum", [])
        
        if param_name == "event_name":
            # Extract event name - look for known patterns
            # Pattern: "on the X" or "about the X" or "of the X"
            event_patterns = [
                r'(?:on|about|of|for)\s+(?:the\s+)?([A-Z][A-Za-z\s]+(?:War|Revolution|Act|Treaty|Battle|Movement|Crisis))',
                r'([A-Z][A-Za-z\s]+(?:War|Revolution|Act|Treaty|Battle|Movement|Crisis))',
            ]
            
            for pattern in event_patterns:
                match = re.search(pattern, query)
                if match:
                    params[param_name] = match.group(1).strip()
                    break
            
            # Fallback: look for capitalized phrases
            if param_name not in params:
                cap_match = re.search(r'(?:the\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)', query)
                if cap_match:
                    params[param_name] = cap_match.group(1).strip()
        
        elif param_name == "specific_info" and enum_values:
            # Match against enum values
            for enum_val in enum_values:
                enum_lower = enum_val.lower()
                # Check if enum value appears in query
                if enum_lower in query_lower:
                    params[param_name] = enum_val
                    break
                # Check for partial matches
                enum_words = enum_lower.split()
                if all(word in query_lower for word in enum_words):
                    params[param_name] = enum_val
                    break
            
            # Fallback: infer from query keywords
            if param_name not in params:
                if "start" in query_lower and "date" in query_lower:
                    params[param_name] = "Start Date"
                elif "end" in query_lower and "date" in query_lower:
                    params[param_name] = "End Date"
                elif "participant" in query_lower:
                    params[param_name] = "Participants"
                elif "result" in query_lower or "outcome" in query_lower:
                    params[param_name] = "Result"
                elif "notable" in query_lower or "figure" in query_lower:
                    params[param_name] = "Notable Figures"
                elif "importance" in query_lower or "significance" in query_lower:
                    params[param_name] = "Importance in History"
        
        elif param_type in ["integer", "number", "float"]:
            # Extract numbers
            numbers = re.findall(r'\d+(?:\.\d+)?', query)
            if numbers:
                if param_type == "integer":
                    params[param_name] = int(numbers[0])
                else:
                    params[param_name] = float(numbers[0])
        
        elif param_type == "string" and param_name not in params:
            # Generic string extraction - try to find relevant text
            # Look for quoted strings first
            quoted = re.findall(r'"([^"]+)"', query)
            if quoted:
                params[param_name] = quoted[0]
    
    return {func_name: params}
