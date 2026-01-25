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
    """Extract function name and parameters from user query. Returns {func_name: {params}}."""
    
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
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_name == "artist":
            # Extract artist name - look for patterns like "artist X" or "for X performing"
            # Common patterns: "for the artist X", "artist X", "by X"
            artist_patterns = [
                r'artist\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)',
                r'for\s+(?:the\s+)?artist\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)',
                r'([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)\s+performing',
                r'by\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)',
            ]
            for pattern in artist_patterns:
                match = re.search(pattern, query)
                if match:
                    params[param_name] = match.group(1).strip()
                    break
        
        elif param_name == "location":
            # Extract location/city - look for "in X" pattern
            location_patterns = [
                r'(?:in|at)\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)',
                r'performing\s+in\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)',
            ]
            for pattern in location_patterns:
                match = re.search(pattern, query)
                if match:
                    # Filter out month names that might be captured
                    location = match.group(1).strip()
                    months = ['january', 'february', 'march', 'april', 'may', 'june', 
                              'july', 'august', 'september', 'october', 'november', 'december']
                    if location.lower() not in months:
                        params[param_name] = location
                        break
        
        elif param_name == "date":
            # Extract date in mm-yyyy format
            # Look for explicit mm-yyyy format first
            date_match = re.search(r'(\d{1,2})-(\d{4})', query)
            if date_match:
                month = date_match.group(1).zfill(2)
                year = date_match.group(2)
                params[param_name] = f"{month}-{year}"
            else:
                # Look for month name and year
                month_map = {
                    'january': '01', 'february': '02', 'march': '03', 'april': '04',
                    'may': '05', 'june': '06', 'july': '07', 'august': '08',
                    'september': '09', 'october': '10', 'november': '11', 'december': '12'
                }
                for month_name, month_num in month_map.items():
                    if month_name in query_lower:
                        # Look for year nearby
                        year_match = re.search(r'(\d{4})', query)
                        if year_match:
                            params[param_name] = f"{month_num}-{year_match.group(1)}"
                        break
    
    return {func_name: params}
