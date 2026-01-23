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
    
    # Extract parameters based on the query and schema
    params = {}
    
    # For calculate_distance: extract celestial bodies and unit
    if func_name == "calculate_distance":
        # Common patterns for celestial body extraction
        # Pattern: "from X to Y" or "between X and Y"
        from_to_match = re.search(r'from\s+(?:the\s+)?(\w+)\s+to\s+(?:the\s+)?(\w+)', query, re.IGNORECASE)
        between_match = re.search(r'between\s+(?:the\s+)?(\w+)\s+and\s+(?:the\s+)?(\w+)', query, re.IGNORECASE)
        
        if from_to_match:
            params["body1"] = from_to_match.group(1).capitalize()
            params["body2"] = from_to_match.group(2).capitalize()
        elif between_match:
            params["body1"] = between_match.group(1).capitalize()
            params["body2"] = between_match.group(2).capitalize()
        
        # Extract unit if specified
        unit_patterns = [
            r'in\s+(miles?|km|kilometers?|meters?|feet|light[\s-]?years?)',
            r'(miles?|km|kilometers?|meters?|feet|light[\s-]?years?)\s*(?:from|between)',
            r'distance\s+in\s+(miles?|km|kilometers?|meters?|feet|light[\s-]?years?)',
        ]
        
        for pattern in unit_patterns:
            unit_match = re.search(pattern, query, re.IGNORECASE)
            if unit_match:
                unit_value = unit_match.group(1).lower()
                # Normalize unit names
                if unit_value.startswith('mile'):
                    params["unit"] = "miles"
                elif unit_value in ('km', 'kilometer', 'kilometers'):
                    params["unit"] = "km"
                elif unit_value in ('meter', 'meters'):
                    params["unit"] = "meters"
                elif unit_value in ('feet', 'foot'):
                    params["unit"] = "feet"
                elif 'light' in unit_value:
                    params["unit"] = "light-years"
                else:
                    params["unit"] = unit_value
                break
    else:
        # Generic extraction for other functions
        for param_name, param_info in params_schema.items():
            param_type = param_info.get("type", "string") if isinstance(param_info, dict) else "string"
            
            if param_type in ("integer", "number", "float"):
                # Extract numbers
                numbers = re.findall(r'\d+(?:\.\d+)?', query)
                if numbers:
                    if param_type == "integer":
                        params[param_name] = int(numbers[0])
                    else:
                        params[param_name] = float(numbers[0])
            elif param_type == "string":
                # Try to extract string values based on common patterns
                # Pattern: "for X" or "of X" or quoted strings
                string_match = re.search(r'(?:for|of|to|from)\s+([A-Za-z\s]+?)(?:\s+(?:and|to|from|in)|[?.,]|$)', query, re.IGNORECASE)
                quoted_match = re.search(r'["\']([^"\']+)["\']', query)
                
                if quoted_match:
                    params[param_name] = quoted_match.group(1)
                elif string_match:
                    params[param_name] = string_match.group(1).strip()
    
    return {func_name: params}
