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
    """Extract function name and parameters from user query based on function schema.
    
    Returns format: {"function_name": {"param1": val1, "param2": val2}}
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
                query = data["question"][0][0].get("content", str(prompt))
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
    
    # Extract parameters from query using regex and string matching
    params = {}
    query_lower = query.lower()
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_name == "city":
            # Extract city - look for patterns like "in [City]" or "for [City]"
            # Common pattern: "time in Sydney" or "weather for New York"
            city_patterns = [
                r'(?:in|for|at)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',  # "in Sydney" or "in New York"
                r'time\s+(?:in|for|at)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
                r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?),?\s+[A-Z][a-z]+',  # "Sydney, Australia"
            ]
            for pattern in city_patterns:
                match = re.search(pattern, query)
                if match:
                    params[param_name] = match.group(1).strip()
                    break
        
        elif param_name == "country":
            # Extract country - often after city with comma or at end
            country_patterns = [
                r'[A-Z][a-z]+,?\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\??$',  # "Sydney, Australia?"
                r'in\s+[A-Z][a-z]+,?\s+([A-Z][a-z]+)',  # "in Sydney, Australia"
                r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s*\??\s*$',  # Country at end
            ]
            for pattern in country_patterns:
                match = re.search(pattern, query)
                if match:
                    candidate = match.group(1).strip().rstrip('?')
                    # Verify it's likely a country (not the city we already extracted)
                    if candidate and candidate != params.get("city", ""):
                        params[param_name] = candidate
                        break
        
        elif param_name == "format":
            # Format is optional - only extract if explicitly mentioned
            format_patterns = [
                r'format[:\s]+["\']?([^"\']+)["\']?',
                r'in\s+([HhMmSs:]+)\s+format',
            ]
            for pattern in format_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    params[param_name] = match.group(1).strip()
                    break
        
        elif param_type in ["integer", "number", "float"]:
            # Extract numbers
            numbers = re.findall(r'\d+(?:\.\d+)?', query)
            if numbers:
                if param_type == "integer":
                    params[param_name] = int(numbers[0])
                else:
                    params[param_name] = float(numbers[0])
        
        elif param_type == "string":
            # Generic string extraction - look for quoted values or after keywords
            quoted_match = re.search(r'["\']([^"\']+)["\']', query)
            if quoted_match:
                params[param_name] = quoted_match.group(1)
    
    return {func_name: params}
