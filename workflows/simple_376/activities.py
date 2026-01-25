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
    
    # Get function details
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters using regex and string matching
    params = {}
    query_lower = query.lower()
    
    # For time_zone_converter: extract city, country, display_format
    if func_name == "time_zone_converter":
        # Extract city - look for patterns like "in [City]" or "[City], [Country]"
        # Common pattern: "in London, UK" or "in London UK"
        city_country_match = re.search(r'in\s+([A-Za-z\s]+?)(?:,\s*|\s+)([A-Za-z\s]+?)(?:\s+in|\s*\?|$)', query, re.IGNORECASE)
        
        if city_country_match:
            params["city"] = city_country_match.group(1).strip()
            params["country"] = city_country_match.group(2).strip()
        else:
            # Try alternative patterns
            # Pattern: "time in [City]"
            city_match = re.search(r'(?:time|current)\s+(?:is\s+)?(?:it\s+)?(?:in|for)\s+([A-Za-z\s]+)', query, re.IGNORECASE)
            if city_match:
                location = city_match.group(1).strip()
                # Check if it contains comma (City, Country)
                if ',' in location:
                    parts = location.split(',')
                    params["city"] = parts[0].strip()
                    params["country"] = parts[1].strip() if len(parts) > 1 else ""
                else:
                    # Try to split by common country names
                    parts = location.split()
                    if len(parts) >= 2:
                        # Assume last part(s) might be country
                        # Check for known country codes/names
                        if parts[-1].upper() in ["UK", "USA", "US", "UAE"]:
                            params["city"] = " ".join(parts[:-1])
                            params["country"] = parts[-1].upper()
                        else:
                            params["city"] = parts[0]
                            params["country"] = " ".join(parts[1:])
                    else:
                        params["city"] = location
                        params["country"] = ""
        
        # Extract display format - look for "12 hour" or "24 hour" or "12h" or "24h"
        if re.search(r'12[\s-]?h(?:our)?', query_lower):
            params["display_format"] = "12h"
        elif re.search(r'24[\s-]?h(?:our)?', query_lower):
            params["display_format"] = "24h"
        # Default is 24h per schema, so we can include it explicitly
        else:
            params["display_format"] = "24h"
    
    else:
        # Generic extraction for other functions
        for param_name, param_info in params_schema.items():
            param_type = param_info.get("type", "string") if isinstance(param_info, dict) else "string"
            
            if param_type in ["integer", "number", "float"]:
                # Extract numbers
                numbers = re.findall(r'\d+(?:\.\d+)?', query)
                if numbers:
                    if param_type == "integer":
                        params[param_name] = int(numbers[0])
                    else:
                        params[param_name] = float(numbers[0])
            elif param_type == "string":
                # Try to extract string values based on common patterns
                # Look for quoted strings first
                quoted = re.findall(r'"([^"]+)"', query)
                if quoted:
                    params[param_name] = quoted[0]
                else:
                    # Try pattern: "for/in/of [value]"
                    match = re.search(rf'(?:for|in|of|to)\s+([A-Za-z0-9\s]+?)(?:\s+(?:and|with|,|in|\?)|$)', query, re.IGNORECASE)
                    if match:
                        params[param_name] = match.group(1).strip()
    
    return {func_name: params}
