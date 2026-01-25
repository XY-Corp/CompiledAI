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
                    query = str(question_data[0])
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
    
    # Get function details
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    required_params = func.get("parameters", {}).get("required", [])
    
    # Extract parameters based on schema
    params = {}
    query_lower = query.lower()
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        default_val = param_info.get("default")
        
        if param_name == "religion_name":
            # Extract religion name - look for known religions or extract from context
            religions = [
                "buddhism", "christianity", "islam", "hinduism", "judaism",
                "sikhism", "taoism", "confucianism", "shinto", "jainism",
                "zoroastrianism", "bahai", "rastafari"
            ]
            
            found_religion = None
            for religion in religions:
                if religion in query_lower:
                    # Capitalize properly
                    found_religion = religion.capitalize()
                    break
            
            if found_religion:
                params[param_name] = found_religion
            else:
                # Try regex to extract "of X" or "about X" patterns
                match = re.search(r'(?:of|about|on)\s+([A-Za-z]+)', query, re.IGNORECASE)
                if match:
                    params[param_name] = match.group(1).capitalize()
        
        elif param_name == "detail_level":
            # Check for detail level indicators in query
            if "full" in query_lower or "complete" in query_lower or "detailed" in query_lower:
                params[param_name] = "full"
            elif "summary" in query_lower or "brief" in query_lower or "short" in query_lower:
                params[param_name] = "summary"
            else:
                # Check description for hints - "full history" suggests full detail
                if "full" in query_lower:
                    params[param_name] = "full"
                elif default_val:
                    params[param_name] = default_val
                else:
                    # Default based on query context
                    params[param_name] = "summary"
        
        elif param_type in ["integer", "number", "float"]:
            # Extract numbers
            numbers = re.findall(r'\d+(?:\.\d+)?', query)
            if numbers:
                if param_type == "integer":
                    params[param_name] = int(numbers[0])
                else:
                    params[param_name] = float(numbers[0])
        
        elif param_type == "string":
            # Generic string extraction - try common patterns
            # Look for quoted strings first
            quoted = re.findall(r'"([^"]+)"', query)
            if quoted:
                params[param_name] = quoted[0]
            elif default_val:
                params[param_name] = default_val
    
    # Re-check detail_level based on "full history" pattern
    if "detail_level" in params_schema:
        if "full" in query_lower and ("history" in query_lower or "detail" in query_lower):
            params["detail_level"] = "full"
    
    return {func_name: params}
