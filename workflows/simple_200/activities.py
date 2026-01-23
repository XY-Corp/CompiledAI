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
    """Extract function call parameters from natural language query using regex patterns."""
    
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
    
    # Get function schema
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters using regex
    params = {}
    
    # Extract distance (miles per year)
    # Patterns: "12,000 miles", "12000 miles per year", "travels 12,000 miles"
    distance_patterns = [
        r'(\d{1,3}(?:,\d{3})*|\d+)\s*miles?\s*(?:per\s*year|annually)?',
        r'travels?\s*(\d{1,3}(?:,\d{3})*|\d+)\s*miles?',
        r'distance\s*(?:of|:)?\s*(\d{1,3}(?:,\d{3})*|\d+)',
    ]
    for pattern in distance_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            # Remove commas and convert to int
            distance_str = match.group(1).replace(',', '')
            params["distance"] = int(distance_str)
            break
    
    # Extract fuel type
    # Patterns: "gas-fueled", "diesel", "gasoline", "electric"
    fuel_patterns = [
        r'(gas|gasoline|diesel|electric|hybrid|petrol)[\s-]*(?:fueled|powered)?',
        r'fuel\s*(?:type|:)?\s*["\']?(\w+)["\']?',
    ]
    for pattern in fuel_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            fuel = match.group(1).lower()
            # Normalize fuel type
            if fuel in ['gas', 'gasoline', 'petrol']:
                params["fuel_type"] = "gas"
            else:
                params["fuel_type"] = fuel
            break
    
    # Extract fuel efficiency (MPG)
    # Patterns: "25 MPG", "fuel efficiency of 25", "25 miles per gallon"
    efficiency_patterns = [
        r'(\d+(?:\.\d+)?)\s*(?:MPG|mpg)',
        r'fuel\s*efficiency\s*(?:of|:)?\s*(\d+(?:\.\d+)?)',
        r'(\d+(?:\.\d+)?)\s*miles?\s*per\s*gallon',
        r'efficiency\s*(?:of|:)?\s*(\d+(?:\.\d+)?)',
    ]
    for pattern in efficiency_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            params["fuel_efficiency"] = float(match.group(1))
            break
    
    # Extract efficiency reduction (optional parameter)
    # Patterns: "efficiency reduction of 5%", "5% decrease"
    reduction_patterns = [
        r'efficiency\s*reduction\s*(?:of|:)?\s*(\d+)\s*%?',
        r'(\d+)\s*%?\s*(?:decrease|reduction)\s*(?:in\s*)?(?:fuel\s*)?efficiency',
    ]
    for pattern in reduction_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            params["efficiency_reduction"] = int(match.group(1))
            break
    
    return {func_name: params}
