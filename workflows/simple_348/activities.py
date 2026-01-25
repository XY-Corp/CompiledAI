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
    """Extract function name and parameters from user query using regex and string matching."""
    
    # Parse prompt (may be JSON string with nested structure)
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
            # Handle BFCL format: {"question": [[{"role": "user", "content": "..."}]], ...}
            if "question" in data and isinstance(data["question"], list):
                if len(data["question"]) > 0 and isinstance(data["question"][0], list):
                    query = data["question"][0][0].get("content", str(prompt))
                else:
                    query = str(prompt)
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
    
    # Extract parameters from query using regex and string matching
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        
        if param_name == "player_name":
            # Extract player name - look for patterns like "name 'X'" or "named 'X'"
            name_match = re.search(r"(?:name|named)\s+['\"]([^'\"]+)['\"]", query, re.IGNORECASE)
            if name_match:
                params[param_name] = name_match.group(1)
        
        elif param_name == "_class":
            # Extract character class - look for patterns like "class 'X'" or "character class 'X'"
            class_match = re.search(r"(?:character\s+)?class\s+['\"]([^'\"]+)['\"]", query, re.IGNORECASE)
            if class_match:
                params[param_name] = class_match.group(1)
        
        elif param_name == "starting_level":
            # Extract starting level - look for patterns like "level to X" or "starting level X"
            level_match = re.search(r"(?:starting\s+)?level\s+(?:to\s+)?(\d+)", query, re.IGNORECASE)
            if level_match:
                params[param_name] = int(level_match.group(1))
    
    return {func_name: params}
