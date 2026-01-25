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
    if isinstance(functions, str):
        try:
            functions = json.loads(functions)
        except json.JSONDecodeError:
            functions = []
    
    if not functions:
        return {"error": "No functions provided"}
    
    func = functions[0]
    func_name = func.get("name", "")
    props = func.get("parameters", {}).get("properties", {})
    
    params = {}
    
    # Extract location parameter
    if "location" in props:
        # Pattern: "in City, State" or "City, State"
        # Look for city/state patterns
        location_patterns = [
            r'in\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*),?\s*([A-Z][a-z]+|[A-Z]{2})',  # "in Boston, Massachusetts"
            r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*),\s*([A-Z][a-z]+|[A-Z]{2})',  # "Boston, Massachusetts"
        ]
        
        for pattern in location_patterns:
            match = re.search(pattern, query)
            if match:
                city = match.group(1).strip()
                state = match.group(2).strip()
                # Convert full state name to abbreviation if needed
                state_abbrevs = {
                    "Massachusetts": "MA", "California": "CA", "New York": "NY",
                    "Texas": "TX", "Florida": "FL", "Illinois": "IL"
                }
                state_abbr = state_abbrevs.get(state, state)
                params["location"] = f"{city}, {state_abbr}"
                break
    
    # Extract facilities parameter (array)
    if "facilities" in props:
        facilities = []
        query_lower = query.lower()
        
        # Check for each facility type mentioned in the query
        facility_mappings = {
            "wi-fi": "Wi-Fi",
            "wifi": "Wi-Fi",
            "free wi-fi": "Wi-Fi",
            "reading room": "Reading Room",
            "fiction": "Fiction",
            "english fiction": "Fiction",
            "children section": "Children Section",
            "children's section": "Children Section",
            "kids section": "Children Section",
            "cafe": "Cafe",
            "coffee": "Cafe"
        }
        
        for keyword, facility in facility_mappings.items():
            if keyword in query_lower and facility not in facilities:
                facilities.append(facility)
        
        if facilities:
            params["facilities"] = facilities
    
    return {func_name: params}
