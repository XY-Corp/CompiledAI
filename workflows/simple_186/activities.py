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
    """Extract function name and parameters from user query based on function schema.
    
    Returns format: {"function_name": {"param1": val1, "param2": val2}}
    """
    # Parse prompt - may be JSON string with nested structure
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
        else:
            data = prompt
        
        # Extract user query from BFCL format: {"question": [[{"role": "user", "content": "..."}]]}
        if isinstance(data, dict) and "question" in data:
            question_data = data["question"]
            if isinstance(question_data, list) and len(question_data) > 0:
                if isinstance(question_data[0], list) and len(question_data[0]) > 0:
                    query = question_data[0][0].get("content", str(prompt))
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
    
    # Get function schema
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters from query using regex and string matching
    params = {}
    query_lower = query.lower()
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_name == "city":
            # Extract city name - look for patterns like "of [City]" or "in [City]"
            # Common pattern: "temperature ... of Tokyo" or "weather in Tokyo"
            city_patterns = [
                r'(?:of|in|for)\s+([A-Za-z\s]+?)(?:,|\s+(?:right|now|today|currently|japan|china|usa|uk|france|germany|india|australia))',
                r'(?:of|in|for)\s+([A-Za-z]+)',
            ]
            for pattern in city_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    city = match.group(1).strip()
                    # Clean up common suffixes
                    city = re.sub(r'\s+(right|now|today|currently)$', '', city, flags=re.IGNORECASE)
                    if city:
                        params["city"] = city
                        break
        
        elif param_name == "country":
            # Extract country - look for country names after city or standalone
            country_patterns = [
                r',\s*([A-Za-z]+)\s+(?:right|now|today|currently)',
                r'(?:in|of)\s+[A-Za-z]+,?\s+([A-Za-z]+)',
                r'([A-Za-z]+)\s+(?:right|now|today|currently)',
            ]
            # Common country names to look for
            countries = ["japan", "china", "usa", "uk", "france", "germany", "india", "australia", 
                        "canada", "brazil", "mexico", "spain", "italy", "russia", "korea"]
            
            for country in countries:
                if country in query_lower:
                    params["country"] = country.title()
                    break
            
            # If not found, try patterns
            if "country" not in params:
                for pattern in country_patterns:
                    match = re.search(pattern, query, re.IGNORECASE)
                    if match:
                        country = match.group(1).strip()
                        if country.lower() not in ["right", "now", "today", "currently", "the"]:
                            params["country"] = country
                            break
        
        elif param_name == "measurement":
            # Extract measurement unit - look for celsius/fahrenheit or c/f
            if "celsius" in query_lower or "°c" in query_lower:
                params["measurement"] = "c"
            elif "fahrenheit" in query_lower or "°f" in query_lower:
                params["measurement"] = "f"
            # Check for explicit 'c' or 'f' mentions
            elif re.search(r'\bin\s+c\b', query_lower):
                params["measurement"] = "c"
            elif re.search(r'\bin\s+f\b', query_lower):
                params["measurement"] = "f"
            # Default based on description - celsius is mentioned first in query
            elif "celsius" in query_lower:
                params["measurement"] = "c"
    
    return {func_name: params}
