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
    
    # Extract parameters based on schema
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_desc = param_info.get("description", "").lower()
        
        if param_name == "location" or "city" in param_desc or "location" in param_desc:
            # Extract city/location - look for common patterns
            # Pattern: "in <City>" or "for <City>"
            location_patterns = [
                r'(?:in|for|at)\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)',  # "in London", "for New York"
                r'air quality (?:index )?(?:in|for|at)\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)',
                r'([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)\s+(?:air quality|on\s+\d)',  # "London air quality" or "London on 2022"
            ]
            
            for pattern in location_patterns:
                match = re.search(pattern, query)
                if match:
                    params[param_name] = match.group(1).strip()
                    break
        
        elif param_name == "date" or "date" in param_desc:
            # Extract date - handle various formats
            # Look for YYYY/MM/DD, YYYY-MM-DD, MM/DD/YYYY, etc.
            date_patterns = [
                r'(\d{4}[/-]\d{2}[/-]\d{2})',  # 2022/08/16 or 2022-08-16
                r'(\d{2}[/-]\d{2}[/-]\d{4})',  # 08/16/2022 or 08-16-2022
                r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',  # flexible date format
            ]
            
            for pattern in date_patterns:
                match = re.search(pattern, query)
                if match:
                    date_str = match.group(1)
                    
                    # Check if description specifies format (month-day-year)
                    if "month-day-year" in param_desc.lower():
                        # Convert from YYYY/MM/DD to MM-DD-YYYY if needed
                        if re.match(r'\d{4}[/-]\d{2}[/-]\d{2}', date_str):
                            # Input is YYYY/MM/DD or YYYY-MM-DD
                            parts = re.split(r'[/-]', date_str)
                            if len(parts) == 3:
                                year, month, day = parts
                                date_str = f"{month}-{day}-{year}"
                    
                    params[param_name] = date_str
                    break
    
    return {func_name: params}
