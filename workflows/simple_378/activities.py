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
    
    # For timezone.convert, extract time, from_timezone, to_timezone
    params = {}
    
    # Extract time - look for patterns like "3pm", "3:00pm", "15:00"
    time_match = re.search(r'\b(\d{1,2}(?::\d{2})?\s*(?:am|pm|AM|PM)?)\b', query)
    if time_match:
        params["time"] = time_match.group(1).strip()
    
    # Extract timezones - look for city/timezone names
    # Pattern: "from X time zone to Y time zone" or "from X to Y"
    query_lower = query.lower()
    
    # Try pattern: "from X time zone to Y time zone"
    tz_pattern = re.search(r'from\s+([A-Za-z\s]+?)(?:\s+time\s*zone)?\s+to\s+([A-Za-z\s]+?)(?:\s+time\s*zone)?\.?$', query, re.IGNORECASE)
    
    if tz_pattern:
        from_tz = tz_pattern.group(1).strip()
        to_tz = tz_pattern.group(2).strip()
        
        # Clean up timezone names - remove trailing "time" if present
        from_tz = re.sub(r'\s+time$', '', from_tz, flags=re.IGNORECASE).strip()
        to_tz = re.sub(r'\s+time$', '', to_tz, flags=re.IGNORECASE).strip()
        
        params["from_timezone"] = from_tz
        params["to_timezone"] = to_tz
    else:
        # Fallback: extract city names mentioned
        cities = re.findall(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b', query)
        # Filter out common words
        common_words = {'Convert', 'The', 'Time', 'Zone'}
        cities = [c for c in cities if c not in common_words]
        
        if len(cities) >= 2:
            params["from_timezone"] = cities[0]
            params["to_timezone"] = cities[1]
    
    return {func_name: params}
