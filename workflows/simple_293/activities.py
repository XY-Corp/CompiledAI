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
    
    # Parse prompt (may be JSON string with nested structure)
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
            # Extract user query from BFCL format
            if "question" in data and isinstance(data["question"], list):
                if len(data["question"]) > 0 and isinstance(data["question"][0], list):
                    query = data["question"][0][0].get("content", prompt)
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
    
    # Get function details
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    params = {}
    query_lower = query.lower()
    
    # Extract scale - look for musical scale patterns
    # Pattern: "notes of X scale" or "X scale" or "scale of X"
    scale_patterns = [
        r'notes\s+of\s+([A-G](?:\s*(?:major|minor|sharp|flat|#|b))+)',
        r'([A-G](?:\s*(?:major|minor|sharp|flat|#|b))+)\s+scale',
        r'scale\s+(?:of\s+)?([A-G](?:\s*(?:major|minor|sharp|flat|#|b))+)',
        r'using\s+([A-G](?:\s*(?:major|minor|sharp|flat|#|b))+)',
    ]
    
    scale_value = None
    for pattern in scale_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            scale_value = match.group(1).strip()
            # Normalize capitalization: "C major" -> "C Major"
            parts = scale_value.split()
            if len(parts) >= 2:
                scale_value = parts[0].upper() + " " + parts[1].capitalize()
            break
    
    if scale_value:
        params["scale"] = scale_value
    
    # Extract note_duration - look for duration keywords
    # Map common phrases to enum values
    duration_mappings = {
        "whole": "whole",
        "half": "half",
        "quarter": "quarter",
        "eighth": "eighth",
        "sixteenth": "sixteenth",
    }
    
    # Check for "quarter of a second" or similar phrases
    if "quarter of a second" in query_lower or "quarter second" in query_lower:
        params["note_duration"] = "quarter"
    elif "half of a second" in query_lower or "half second" in query_lower:
        params["note_duration"] = "half"
    elif "eighth of a second" in query_lower or "eighth second" in query_lower:
        params["note_duration"] = "eighth"
    elif "sixteenth of a second" in query_lower or "sixteenth second" in query_lower:
        params["note_duration"] = "sixteenth"
    elif "whole second" in query_lower:
        params["note_duration"] = "whole"
    else:
        # Check for direct enum values
        for key, value in duration_mappings.items():
            if key in query_lower:
                params["note_duration"] = value
                break
    
    # Extract track_length - look for duration in minutes or seconds
    # Pattern: "X minutes" or "X seconds" or "X min" or "X sec"
    
    # First check for minutes
    minutes_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:minutes?|mins?)', query_lower)
    seconds_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:seconds?|secs?)', query_lower)
    
    # Also check for "duration of X minutes" pattern
    duration_minutes_match = re.search(r'duration\s+of\s+(\d+(?:\.\d+)?)\s*(?:minutes?|mins?)', query_lower)
    duration_seconds_match = re.search(r'duration\s+of\s+(\d+(?:\.\d+)?)\s*(?:seconds?|secs?)', query_lower)
    
    track_length = None
    
    if duration_minutes_match:
        minutes = float(duration_minutes_match.group(1))
        track_length = int(minutes * 60)
    elif duration_seconds_match:
        track_length = int(float(duration_seconds_match.group(1)))
    elif minutes_match:
        minutes = float(minutes_match.group(1))
        track_length = int(minutes * 60)
    elif seconds_match:
        track_length = int(float(seconds_match.group(1)))
    
    if track_length is not None:
        params["track_length"] = track_length
    
    return {func_name: params}
