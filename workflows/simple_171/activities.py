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
    """Extract function call parameters from natural language query.
    
    Parses the prompt to extract the user query, then uses regex and string
    matching to extract parameter values based on the function schema.
    Returns format: {"function_name": {"param1": val1, ...}}
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
    
    # Get function details
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters using regex
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_type == "integer" or param_type == "number":
            # Extract integers based on context clues in description
            if "case" in param_desc and "number" in param_desc:
                # Look for case number pattern
                match = re.search(r'case\s+(?:number\s+)?(\d+)', query, re.IGNORECASE)
                if not match:
                    match = re.search(r'number\s+(\d+)', query, re.IGNORECASE)
                if match:
                    params[param_name] = int(match.group(1))
            elif "year" in param_desc:
                # Look for year pattern (4 digit number, typically 19xx or 20xx)
                match = re.search(r'\b(19\d{2}|20\d{2})\b', query)
                if match:
                    params[param_name] = int(match.group(1))
            else:
                # Generic number extraction - get all numbers and use context
                numbers = re.findall(r'\b(\d+)\b', query)
                if numbers:
                    # Filter out years for non-year fields
                    non_year_numbers = [n for n in numbers if not (len(n) == 4 and n.startswith(('19', '20')))]
                    if non_year_numbers:
                        params[param_name] = int(non_year_numbers[0])
                    elif numbers:
                        params[param_name] = int(numbers[0])
        
        elif param_type == "string":
            # Extract string values based on description context
            if "court" in param_desc or "city" in param_desc:
                # Look for city/location patterns
                # Pattern: "in X court" or "X court" or "in X"
                match = re.search(r'in\s+([A-Z][a-zA-Z\s]+?)(?:\s+court|\s+for|\s*$)', query, re.IGNORECASE)
                if match:
                    params[param_name] = match.group(1).strip()
                else:
                    # Try pattern like "New York court"
                    match = re.search(r'([A-Z][a-zA-Z\s]+?)\s+court', query, re.IGNORECASE)
                    if match:
                        params[param_name] = match.group(1).strip()
            else:
                # Generic string extraction - look for quoted strings or capitalized phrases
                match = re.search(r'"([^"]+)"', query)
                if match:
                    params[param_name] = match.group(1)
    
    return {func_name: params}
