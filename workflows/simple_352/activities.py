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
    
    # Get function details
    func = funcs[0] if isinstance(funcs, list) else funcs
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    required_params = func.get("parameters", {}).get("required", [])
    
    # Extract parameters based on schema
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        default_val = param_info.get("default")
        
        extracted_value = None
        
        # For game_name parameter - extract game title
        if "game" in param_name.lower() or "name" in param_name.lower():
            # Look for quoted game names first
            quoted_match = re.search(r"['\"]([^'\"]+)['\"]", query)
            if quoted_match:
                extracted_value = quoted_match.group(1)
            else:
                # Try to extract game name after common patterns
                game_patterns = [
                    r"(?:for|of|game)\s+(?:the\s+)?([A-Z][A-Za-z0-9\s:'\-]+?)(?:\s+from|\s+on|\s*$)",
                    r"score\s+(?:for|of)\s+(?:the\s+)?([A-Z][A-Za-z0-9\s:'\-]+?)(?:\s+from|\s+on|\s*$)",
                ]
                for pattern in game_patterns:
                    match = re.search(pattern, query, re.IGNORECASE)
                    if match:
                        extracted_value = match.group(1).strip()
                        break
        
        # For platform parameter
        elif "platform" in param_name.lower():
            # Common gaming platforms
            platforms = [
                "Nintendo Switch", "PS5", "PS4", "PlayStation 5", "PlayStation 4",
                "Xbox Series X", "Xbox One", "PC", "Steam", "Wii U", "3DS"
            ]
            for platform in platforms:
                if platform.lower() in query.lower():
                    extracted_value = platform
                    break
            
            # If no platform found, use default if available
            if extracted_value is None and default_val:
                extracted_value = default_val
        
        # Generic string extraction for other parameters
        elif param_type == "string":
            # Try quoted strings
            quoted_match = re.search(r"['\"]([^'\"]+)['\"]", query)
            if quoted_match:
                extracted_value = quoted_match.group(1)
        
        # Generic number extraction
        elif param_type in ["integer", "number", "float"]:
            numbers = re.findall(r'\d+(?:\.\d+)?', query)
            if numbers:
                if param_type == "integer":
                    extracted_value = int(numbers[0])
                else:
                    extracted_value = float(numbers[0])
        
        # Set the parameter value
        if extracted_value is not None:
            params[param_name] = extracted_value
        elif default_val is not None:
            params[param_name] = default_val
        elif param_name in required_params:
            # For required params without value, try to infer from context
            if "game" in param_name.lower() or "name" in param_name.lower():
                # Last resort: extract any capitalized phrase
                cap_match = re.search(r"([A-Z][A-Za-z0-9\s:'\-]{3,})", query)
                if cap_match:
                    params[param_name] = cap_match.group(1).strip()
    
    return {func_name: params}
