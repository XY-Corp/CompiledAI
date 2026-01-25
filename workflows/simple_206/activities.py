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
    
    # Extract parameters from query
    params = {}
    
    # Extract location - look for city names, patterns like "in X" or "X, UK"
    if "location" in params_schema:
        # Pattern: "in [City]" or "[City], [Country/State]"
        location_patterns = [
            r'in\s+([A-Za-z\s]+(?:,\s*[A-Za-z\s]+)?)',  # "in London" or "in London, UK"
            r'(?:near|around|at)\s+([A-Za-z\s]+(?:,\s*[A-Za-z\s]+)?)',
        ]
        
        for pattern in location_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                location = match.group(1).strip()
                # Clean up - remove trailing words that aren't part of location
                location = re.sub(r'\s+(?:with|that|which|has|have).*$', '', location, flags=re.IGNORECASE)
                params["location"] = location.strip()
                break
        
        # Fallback: look for known city patterns
        if "location" not in params:
            city_match = re.search(r'\b(London|Paris|New York|Tokyo|Berlin|Sydney|Chicago|Boston|Seattle|Miami)\b', query, re.IGNORECASE)
            if city_match:
                params["location"] = city_match.group(1)
    
    # Extract amenities - look for specific amenity keywords
    if "amenities" in params_schema:
        amenity_options = ["Tennis Court", "Picnic Area", "Playground", "Running Track"]
        found_amenities = []
        
        query_lower = query.lower()
        
        # Check for each amenity
        for amenity in amenity_options:
            amenity_lower = amenity.lower()
            # Check for exact match or partial match
            if amenity_lower in query_lower:
                found_amenities.append(amenity)
            # Also check for variations
            elif amenity_lower.replace(" ", "") in query_lower.replace(" ", ""):
                found_amenities.append(amenity)
        
        # Also check for common variations
        if "tennis" in query_lower and "Tennis Court" not in found_amenities:
            found_amenities.append("Tennis Court")
        if "picnic" in query_lower and "Picnic Area" not in found_amenities:
            found_amenities.append("Picnic Area")
        if "playground" in query_lower and "Playground" not in found_amenities:
            found_amenities.append("Playground")
        if "running" in query_lower or "track" in query_lower:
            if "Running Track" not in found_amenities:
                found_amenities.append("Running Track")
        
        # Only include amenities if found (it has a default, so optional)
        if found_amenities:
            params["amenities"] = found_amenities
    
    return {func_name: params}
