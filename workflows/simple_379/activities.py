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
    
    # Parse prompt - may be JSON string with nested structure
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
        else:
            data = prompt
        
        # Extract user query from BFCL format: {"question": [[{"role": "user", "content": "..."}]]}
        if isinstance(data, dict) and "question" in data:
            question_data = data.get("question", [])
            if isinstance(question_data, list) and len(question_data) > 0:
                first_item = question_data[0]
                if isinstance(first_item, list) and len(first_item) > 0:
                    query = first_item[0].get("content", str(prompt))
                elif isinstance(first_item, dict):
                    query = first_item.get("content", str(prompt))
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
    
    if not funcs:
        return {"error": "No functions provided"}
    
    # Get function details
    func = funcs[0] if isinstance(funcs, list) else funcs
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {})
    properties = params_schema.get("properties", {})
    required_params = params_schema.get("required", [])
    
    # Extract parameters based on schema
    params = {}
    query_lower = query.lower()
    
    for param_name, param_info in properties.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        # Location extraction patterns
        if param_name == "location" or "city" in param_desc:
            # Pattern: "in [City]" or "for [City]" or "time in [City]"
            location_patterns = [
                r'(?:in|for|at)\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)?)',  # "in Sydney"
                r'time\s+(?:in|for|at)\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)?)',
                r'([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)?),\s*[A-Z]',  # "Sydney, Australia"
            ]
            for pattern in location_patterns:
                match = re.search(pattern, query)
                if match:
                    location = match.group(1).strip()
                    # Filter out country names that might be captured
                    if location.lower() not in ['australia', 'usa', 'uk', 'canada', 'japan', 'china', 'india', 'france', 'germany']:
                        params[param_name] = location
                        break
            
            # Fallback: look for city before comma
            if param_name not in params:
                comma_match = re.search(r'([A-Z][a-zA-Z]+)\s*,', query)
                if comma_match:
                    params[param_name] = comma_match.group(1).strip()
        
        # Country extraction patterns
        elif param_name == "country" or "country" in param_desc:
            # Pattern: "[City], [Country]" or "in [Country]"
            country_patterns = [
                r',\s*([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)?)\s*\??',  # ", Australia?"
                r'([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)?)\s*\??\s*$',  # "Australia?" at end
            ]
            
            # Known countries to match
            known_countries = ['australia', 'usa', 'united states', 'uk', 'united kingdom', 
                             'canada', 'japan', 'china', 'india', 'france', 'germany', 
                             'brazil', 'mexico', 'spain', 'italy', 'russia']
            
            # First try to find known country in query
            for country in known_countries:
                if country in query_lower:
                    # Capitalize properly
                    if country == 'usa':
                        params[param_name] = 'USA'
                    elif country == 'uk':
                        params[param_name] = 'UK'
                    elif country == 'united states':
                        params[param_name] = 'United States'
                    elif country == 'united kingdom':
                        params[param_name] = 'United Kingdom'
                    else:
                        params[param_name] = country.title()
                    break
            
            # Fallback to pattern matching
            if param_name not in params:
                for pattern in country_patterns:
                    match = re.search(pattern, query)
                    if match:
                        country = match.group(1).strip().rstrip('?')
                        # Verify it's likely a country (not a city we already captured)
                        if country.lower() in known_countries or (param_name not in params):
                            params[param_name] = country
                            break
        
        # Timezone extraction (optional parameter)
        elif param_name == "timezone" or "timezone" in param_desc:
            # Look for explicit timezone mentions
            tz_patterns = [
                r'timezone[:\s]+([A-Za-z/_]+)',
                r'tz[:\s]+([A-Za-z/_]+)',
                r'([A-Z]{3,4})\s+time',  # "EST time", "PST time"
            ]
            for pattern in tz_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    params[param_name] = match.group(1).strip()
                    break
        
        # Generic string extraction for other parameters
        elif param_type == "string":
            # Try to extract quoted strings
            quoted_match = re.search(r'"([^"]+)"', query)
            if quoted_match:
                params[param_name] = quoted_match.group(1)
        
        # Number extraction
        elif param_type in ["integer", "number", "float"]:
            numbers = re.findall(r'\d+(?:\.\d+)?', query)
            if numbers:
                if param_type == "integer":
                    params[param_name] = int(numbers[0])
                else:
                    params[param_name] = float(numbers[0])
    
    # Only include required params and params we found values for
    # Don't include optional params without values
    final_params = {}
    for param_name in properties:
        if param_name in params:
            final_params[param_name] = params[param_name]
        elif param_name in required_params:
            # Required but not found - this shouldn't happen with good extraction
            final_params[param_name] = "<UNKNOWN>"
    
    return {func_name: final_params}
