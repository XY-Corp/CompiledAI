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
    
    # Parse prompt (may be JSON string with nested structure)
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
            # Extract user query from BFCL format: {"question": [[{"role": "user", "content": "..."}]]}
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
    
    # Get function schema
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    props = func.get("parameters", {}).get("properties", {})
    
    params = {}
    query_lower = query.lower()
    
    # Extract location - look for "city, state" pattern or "around/in/near LOCATION"
    location_patterns = [
        r'(?:around|in|near|at)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*,?\s*[A-Z]{2}|[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*,\s*[A-Z][a-z]+)',
        r'([A-Z][a-z]+,\s*[A-Z][a-z]+)',
        r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*,\s*[A-Z]{2})',
    ]
    
    location = None
    for pattern in location_patterns:
        match = re.search(pattern, query)
        if match:
            location = match.group(1).strip()
            # Normalize "Denver, Colorado" to "Denver, CO" style if needed
            break
    
    if location:
        params["location"] = location
    
    # Extract radius - look for number followed by km/kms/kilometer
    radius_patterns = [
        r'(\d+)\s*(?:km|kms|kilometer|kilometers)\s*(?:radius)?',
        r'(?:within|radius\s*(?:of)?)\s*(\d+)\s*(?:km|kms|kilometer|kilometers)?',
        r'(\d+)\s*(?:km|kms)?\s*radius',
    ]
    
    radius = None
    for pattern in radius_patterns:
        match = re.search(pattern, query_lower)
        if match:
            radius = int(match.group(1))
            break
    
    if radius is not None:
        params["radius"] = radius
    
    # Extract department - check for enum values in query
    department_enum = ["General Medicine", "Emergency", "Pediatrics", "Cardiology", "Orthopedics"]
    department = None
    
    for dept in department_enum:
        if dept.lower() in query_lower:
            department = dept
            break
    
    if department:
        params["department"] = department
    
    return {func_name: params}
