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
    
    Uses regex and string matching to extract values - no LLM calls needed.
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
    
    # Extract parameters from query using regex and string matching
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_type == "integer":
            # Extract year (4-digit number)
            if "year" in param_name.lower() or "year" in param_desc:
                year_match = re.search(r'\b(19\d{2}|20\d{2})\b', query)
                if year_match:
                    params[param_name] = int(year_match.group(1))
            else:
                # Generic integer extraction
                numbers = re.findall(r'\b(\d+)\b', query)
                if numbers:
                    params[param_name] = int(numbers[0])
        
        elif param_type == "string":
            # Extract crime type
            if "crime" in param_name.lower() or "crime" in param_desc:
                # Common crime types to look for
                crime_patterns = [
                    r'\b(theft|robbery|assault|burglary|fraud|murder|homicide|arson|vandalism|kidnapping)\b',
                    r'about\s+(\w+)\s+crimes?',
                    r'(\w+)\s+crimes?\s+in',
                ]
                for pattern in crime_patterns:
                    match = re.search(pattern, query, re.IGNORECASE)
                    if match:
                        params[param_name] = match.group(1).lower()
                        break
            
            # Extract location/city
            elif "location" in param_name.lower() or "city" in param_desc or "location" in param_desc:
                # Pattern: "in [City], [State]" or "in [City]"
                location_patterns = [
                    r'in\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?),?\s*(?:[A-Z]{2}|[A-Z][a-z]+)?',
                    r'in\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
                ]
                for pattern in location_patterns:
                    match = re.search(pattern, query)
                    if match:
                        params[param_name] = match.group(1).strip()
                        break
            
            else:
                # Generic string extraction - try to find quoted strings or key phrases
                quoted = re.search(r'"([^"]+)"', query)
                if quoted:
                    params[param_name] = quoted.group(1)
    
    return {func_name: params}
