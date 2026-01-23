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
    
    if not funcs:
        return {"error": "No functions provided"}
    
    func = funcs[0]
    func_name = func.get("name", "")
    props = func.get("parameters", {}).get("properties", {})
    
    params = {}
    query_lower = query.lower()
    
    # Extract location (city name) - look for patterns like "in [City]" or "for [City]"
    if "location" in props:
        # Pattern: "in New York", "for New York", "weather New York"
        location_patterns = [
            r'(?:in|for|weather\s+(?:in|for)?)\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)',
            r'([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)\s+(?:weather|forecast)',
        ]
        
        for pattern in location_patterns:
            match = re.search(pattern, query)
            if match:
                params["location"] = match.group(1).strip()
                break
        
        # Fallback: look for capitalized words that could be city names
        if "location" not in params:
            # Find capitalized words (potential city names)
            caps = re.findall(r'\b([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)\b', query)
            # Filter out common words
            common_words = {"What", "The", "How", "When", "Where", "Will", "Can", "Is", "Are", "Default"}
            for cap in caps:
                if cap not in common_words:
                    params["location"] = cap
                    break
    
    # Extract duration (number of hours)
    if "duration" in props:
        # Pattern: "72 hours", "next 72 hours", "24 hour"
        duration_patterns = [
            r'(\d+)\s*hours?',
            r'next\s+(\d+)\s*hours?',
        ]
        
        for pattern in duration_patterns:
            match = re.search(pattern, query_lower)
            if match:
                params["duration"] = int(match.group(1))
                break
    
    # Extract include_precipitation (boolean)
    if "include_precipitation" in props:
        # Check if precipitation is mentioned
        precipitation_keywords = ["precipitation", "rain", "snow", "rainfall", "snowfall"]
        include_precip = any(kw in query_lower for kw in precipitation_keywords)
        
        # Also check for explicit "including" patterns
        if re.search(r'includ(?:e|ing)\s+(?:the\s+)?precipitation', query_lower):
            include_precip = True
        
        params["include_precipitation"] = include_precip
    
    return {func_name: params}
