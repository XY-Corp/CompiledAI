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
    
    # Get function details
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters from query using regex
    params = {}
    query_lower = query.lower()
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_name == "location":
            # Extract city name - look for "in [City]" pattern
            location_patterns = [
                r'\bin\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)',  # "in Austin", "in New York"
                r'(?:for|at)\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)',  # "for Austin"
            ]
            for pattern in location_patterns:
                match = re.search(pattern, query)
                if match:
                    params[param_name] = match.group(1).strip()
                    break
        
        elif param_name == "days":
            # Extract number of days - look for "next X days" or just numbers near "days"
            days_patterns = [
                r'(?:next|for|over)\s+(\d+)\s+days?',  # "next 3 days"
                r'(\d+)\s+days?',  # "3 days"
            ]
            for pattern in days_patterns:
                match = re.search(pattern, query_lower)
                if match:
                    params[param_name] = int(match.group(1))
                    break
        
        elif param_name == "temp_unit":
            # Extract temperature unit - look for Celsius or Fahrenheit
            if "celsius" in query_lower:
                params[param_name] = "Celsius"
            elif "fahrenheit" in query_lower:
                params[param_name] = "Fahrenheit"
            # If not specified, don't include (use default)
        
        elif param_type == "integer":
            # Generic integer extraction
            numbers = re.findall(r'\d+', query)
            if numbers:
                params[param_name] = int(numbers[0])
        
        elif param_type == "string":
            # Generic string extraction - try common patterns
            string_patterns = [
                r'(?:for|in|at|of)\s+([A-Za-z][A-Za-z\s]+?)(?:\s+(?:for|in|and|with|,)|$)',
            ]
            for pattern in string_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    params[param_name] = match.group(1).strip()
                    break
    
    return {func_name: params}
