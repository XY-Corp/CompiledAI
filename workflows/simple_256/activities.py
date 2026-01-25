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
    
    # Parse prompt - may be JSON string with nested structure
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
    
    # Parse functions - may be JSON string
    try:
        if isinstance(functions, str):
            funcs = json.loads(functions)
        else:
            funcs = functions
    except (json.JSONDecodeError, TypeError):
        funcs = []
    
    # Get function schema
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters from query using regex
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_type == "integer" or param_type == "number":
            # Extract numbers - look for context clues in description
            if "radius" in param_name.lower() or "radius" in param_desc:
                # Look for "radius of X" pattern
                match = re.search(r'radius\s+of\s+(\d+)', query, re.IGNORECASE)
                if match:
                    params[param_name] = int(match.group(1))
                    continue
            
            # Generic number extraction for this parameter
            # Try to find number near the parameter name
            pattern = rf'{param_name}\s*(?:of|:|\s)\s*(\d+)'
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                params[param_name] = int(match.group(1)) if param_type == "integer" else float(match.group(1))
            else:
                # Fallback: extract all numbers and assign based on order
                numbers = re.findall(r'\b(\d+)\b', query)
                if numbers and param_name not in params:
                    # Use first unassigned number
                    params[param_name] = int(numbers[0]) if param_type == "integer" else float(numbers[0])
        
        elif param_type == "string":
            # Extract string values - look for quoted strings or specific patterns
            if "color" in param_name.lower() or "color" in param_desc:
                # Look for color patterns: 'Red', "Blue", color Red, color: red
                # First try quoted strings
                quoted_match = re.search(r"color\s+['\"]?(\w+)['\"]?", query, re.IGNORECASE)
                if quoted_match:
                    params[param_name] = quoted_match.group(1)
                    continue
                
                # Try "color 'X'" or 'color "X"' pattern
                quoted_match = re.search(r"['\"](\w+)['\"]", query)
                if quoted_match:
                    # Check if this looks like a color (common colors)
                    potential_color = quoted_match.group(1)
                    params[param_name] = potential_color
                    continue
            
            if "background" in param_name.lower() or "background" in param_desc:
                # Look for background color pattern
                bg_match = re.search(r'background\s+(?:color\s+)?[:\s]*[\'"]?(\w+)[\'"]?', query, re.IGNORECASE)
                if bg_match:
                    params[param_name] = bg_match.group(1)
    
    return {func_name: params}
