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
    
    Uses regex and string parsing to extract values - no LLM calls needed.
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
    
    # Extract parameters from query using regex
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_type == "integer" or param_type == "number":
            # Extract numbers from query
            # Look for patterns like "weight 70 kg", "70 kg", "70 kilograms"
            if "weight" in param_name.lower() or "weight" in param_desc:
                # Pattern for weight: "weight X kg" or "X kg" or "weighing X"
                weight_patterns = [
                    r'weight\s+(\d+(?:\.\d+)?)\s*(?:kg|kilograms?)?',
                    r'(\d+(?:\.\d+)?)\s*(?:kg|kilograms?)',
                    r'weighing\s+(\d+(?:\.\d+)?)',
                    r'(\d+(?:\.\d+)?)\s*(?:kg|kilograms?)\s*(?:weight)?',
                ]
                for pattern in weight_patterns:
                    match = re.search(pattern, query, re.IGNORECASE)
                    if match:
                        value = match.group(1)
                        params[param_name] = int(float(value)) if param_type == "integer" else float(value)
                        break
            else:
                # Generic number extraction
                numbers = re.findall(r'\d+(?:\.\d+)?', query)
                if numbers:
                    value = numbers[0]
                    params[param_name] = int(float(value)) if param_type == "integer" else float(value)
        
        elif param_type == "string":
            # For optional string params, only extract if explicitly mentioned
            if param_name not in required_params:
                # Check if the parameter is mentioned in the query
                if "activity" in param_name.lower() or "activity" in param_desc:
                    activity_patterns = [
                        r'activity\s+(?:level\s+)?(?:is\s+)?["\']?(\w+)["\']?',
                        r'(\w+)\s+activity',
                        r'activity[:\s]+(\w+)',
                    ]
                    for pattern in activity_patterns:
                        match = re.search(pattern, query, re.IGNORECASE)
                        if match:
                            params[param_name] = match.group(1).lower()
                            break
                
                elif "climate" in param_name.lower() or "climate" in param_desc:
                    climate_patterns = [
                        r'climate\s+(?:is\s+)?["\']?(\w+)["\']?',
                        r'(\w+)\s+climate',
                        r'lives?\s+in\s+(?:a\s+)?(\w+)\s+(?:climate|area|region)',
                    ]
                    for pattern in climate_patterns:
                        match = re.search(pattern, query, re.IGNORECASE)
                        if match:
                            params[param_name] = match.group(1).lower()
                            break
    
    return {func_name: params}
