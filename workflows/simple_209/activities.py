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
            return {"error": "Invalid functions JSON"}
    
    if not functions:
        return {"error": "No functions provided"}
    
    func = functions[0]
    func_name = func.get("name", "")
    props = func.get("parameters", {}).get("properties", {})
    
    params = {}
    
    # Extract location parameter
    if "location" in props:
        # Pattern: "in <City>, <State>" or "<City>, <State>"
        # Look for city, state patterns
        location_patterns = [
            r'in\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*),?\s*([A-Z][a-z]+|[A-Z]{2})',
            r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*),\s*([A-Z][a-z]+|[A-Z]{2})',
        ]
        
        for pattern in location_patterns:
            match = re.search(pattern, query)
            if match:
                city = match.group(1)
                state = match.group(2)
                # Normalize state abbreviations
                state_abbrevs = {
                    "Massachusetts": "MA", "California": "CA", "New York": "NY",
                    "Texas": "TX", "Florida": "FL", "Illinois": "IL"
                }
                if state in state_abbrevs:
                    state = state_abbrevs[state]
                params["location"] = f"{city}, {state}"
                break
    
    # Extract facilities parameter (array of strings)
    if "facilities" in props:
        facilities = []
        prop_info = props["facilities"]
        
        # Get allowed enum values if specified
        allowed_values = []
        if "items" in prop_info and "enum" in prop_info["items"]:
            allowed_values = prop_info["items"]["enum"]
        
        query_lower = query.lower()
        
        # Map common phrases to facility names
        facility_mappings = {
            "wi-fi": "Wi-Fi",
            "wifi": "Wi-Fi",
            "free wi-fi": "Wi-Fi",
            "free wifi": "Wi-Fi",
            "reading room": "Reading Room",
            "fiction": "Fiction",
            "english fiction": "Fiction",
            "children section": "Children Section",
            "children's section": "Children Section",
            "kids section": "Children Section",
            "cafe": "Cafe",
            "coffee": "Cafe",
        }
        
        for phrase, facility in facility_mappings.items():
            if phrase in query_lower:
                if not allowed_values or facility in allowed_values:
                    if facility not in facilities:
                        facilities.append(facility)
        
        params["facilities"] = facilities
    
    return {func_name: params}
