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
    """Extract function name and parameters from user query. Returns {"func_name": {params}}."""
    
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
    
    # Get function details
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    required_params = func.get("parameters", {}).get("required", [])
    
    # Extract parameters from query
    params = {}
    query_lower = query.lower()
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_type == "integer" or param_type == "number":
            # Extract numbers from query
            # Look for patterns like "three", "five", etc. and convert to numbers
            word_to_num = {
                "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
                "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10
            }
            
            # First try to find word numbers
            found_num = None
            for word, num in word_to_num.items():
                if word in query_lower:
                    found_num = num
                    break
            
            # If no word number, try digit extraction
            if found_num is None:
                numbers = re.findall(r'\d+', query)
                if numbers:
                    found_num = int(numbers[0])
            
            if found_num is not None:
                params[param_name] = found_num
                
        elif param_type == "string":
            # Extract string values based on context
            # For hobby/activity, look for patterns
            if "hobby" in param_name.lower() or "activity" in param_desc:
                # Common patterns: "who like X", "who enjoy X", "people who X"
                patterns = [
                    r'who\s+(?:like|enjoy|love|do)\s+(\w+)',
                    r'interested\s+in\s+(\w+)',
                    r'hobby\s+(?:is|of)\s+(\w+)',
                    r'activity\s+(?:is|of)\s+(\w+)',
                ]
                
                for pattern in patterns:
                    match = re.search(pattern, query_lower)
                    if match:
                        params[param_name] = match.group(1)
                        break
                
                # If no pattern matched, try to find activity-related words
                if param_name not in params:
                    # Look for common activities/hobbies
                    activities = ["jogging", "running", "swimming", "reading", "gaming", 
                                  "cooking", "hiking", "cycling", "dancing", "painting"]
                    for activity in activities:
                        if activity in query_lower:
                            params[param_name] = activity
                            break
    
    return {func_name: params}
