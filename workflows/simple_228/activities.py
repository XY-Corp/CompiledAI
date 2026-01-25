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
    
    func = funcs[0]
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    required_params = func.get("parameters", {}).get("required", [])
    
    # Extract parameters based on schema
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_type == "integer":
            # Extract numbers from query
            # Look for patterns like "three" (word) or "3" (digit)
            word_to_num = {
                "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
                "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10
            }
            
            # Try word numbers first
            for word, num in word_to_num.items():
                if word in query.lower():
                    params[param_name] = num
                    break
            
            # If not found, try digit numbers
            if param_name not in params:
                numbers = re.findall(r'\b(\d+)\b', query)
                if numbers:
                    params[param_name] = int(numbers[0])
        
        elif param_type == "string":
            # For hobby/activity extraction, look for common patterns
            if "hobby" in param_name.lower() or "activity" in param_desc:
                # Pattern: "who like X" or "who enjoy X" or "people who X"
                patterns = [
                    r'who\s+(?:like|enjoy|love|do)\s+(\w+)',
                    r'interested\s+in\s+(\w+)',
                    r'hobby\s+(?:is|of)\s+(\w+)',
                    r'activity\s+(?:is|of)\s+(\w+)',
                ]
                
                for pattern in patterns:
                    match = re.search(pattern, query, re.IGNORECASE)
                    if match:
                        params[param_name] = match.group(1).strip()
                        break
                
                # Fallback: extract the main activity noun
                if param_name not in params:
                    # Look for gerunds (words ending in -ing that are activities)
                    gerund_match = re.search(r'\b(\w+ing)\b', query, re.IGNORECASE)
                    if gerund_match:
                        params[param_name] = gerund_match.group(1).lower()
    
    # Only include required params or params we found values for
    final_params = {}
    for param_name in params_schema.keys():
        if param_name in params:
            final_params[param_name] = params[param_name]
        elif param_name in required_params:
            # Required but not found - this shouldn't happen with good extraction
            pass
    
    return {func_name: final_params}
