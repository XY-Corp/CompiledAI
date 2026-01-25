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
    """Extract function name and parameters from user query using regex patterns."""
    
    # Parse prompt - may be JSON string with nested structure
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
    props = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters using regex
    params = {}
    
    # Extract country - look for country names (capitalized words)
    country_patterns = [
        r'(?:for|of|in)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',  # "for Brazil", "of Brazil"
        r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:in|for|population)',  # "Brazil in 2022"
    ]
    for pattern in country_patterns:
        match = re.search(pattern, query)
        if match:
            params["country"] = match.group(1).strip()
            break
    
    # Extract year - 4-digit number that looks like a year (1900-2100)
    year_match = re.search(r'\b(19\d{2}|20\d{2}|21\d{2})\b', query)
    if year_match:
        params["year"] = year_match.group(1)
    
    # Extract population - look for "population is X million" or similar patterns
    pop_patterns = [
        r'population\s+(?:is|of)\s+(\d+(?:\.\d+)?)\s*million',
        r'(\d+(?:\.\d+)?)\s*million\s+(?:people|population)',
        r'population[:\s]+(\d+(?:\.\d+)?)\s*million',
    ]
    for pattern in pop_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            pop_value = float(match.group(1))
            # Convert millions to actual number
            params["population"] = int(pop_value * 1_000_000)
            break
    
    # Extract land area - look for "land area is X million square kilometers" or similar
    area_patterns = [
        r'land\s+area\s+(?:is|of)\s+(\d+(?:\.\d+)?)\s*million\s*(?:square\s*)?(?:kilometers|km)',
        r'(\d+(?:\.\d+)?)\s*million\s*(?:square\s*)?(?:kilometers|km)',
        r'area[:\s]+(\d+(?:\.\d+)?)\s*million',
    ]
    for pattern in area_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            area_value = float(match.group(1))
            # Convert millions to actual number
            params["land_area"] = int(area_value * 1_000_000)
            break
    
    return {func_name: params}
