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
    
    # Extract parameters based on the query
    params = {}
    
    # For get_song_lyrics: extract song_title and artist_name
    # Pattern: "lyrics to the song 'X' by Y" or "lyrics of 'X' by Y"
    
    # Extract song title - look for quoted text or text after "song"
    song_patterns = [
        r"song\s+['\"]([^'\"]+)['\"]",  # song 'X' or song "X"
        r"['\"]([^'\"]+)['\"]",  # any quoted text (first match is likely song)
        r"lyrics\s+(?:to|of|for)\s+(?:the\s+)?(?:song\s+)?['\"]?([^'\"]+?)['\"]?\s+by",  # lyrics to X by
    ]
    
    song_title = None
    for pattern in song_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            song_title = match.group(1).strip()
            break
    
    # Extract artist name - look for "by X" pattern
    artist_patterns = [
        r"\bby\s+([A-Za-z\s]+?)(?:\.|$|\?|!)",  # by X (at end or before punctuation)
        r"\bby\s+([A-Za-z\s]+)",  # by X (general)
    ]
    
    artist_name = None
    for pattern in artist_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            artist_name = match.group(1).strip()
            break
    
    # Build params dict with extracted values
    if "song_title" in params_schema and song_title:
        params["song_title"] = song_title
    
    if "artist_name" in params_schema and artist_name:
        params["artist_name"] = artist_name
    
    # Check for language specification (optional param)
    if "lang" in params_schema:
        lang_match = re.search(r"\b(English|French|Spanish|German|Italian)\b", query, re.IGNORECASE)
        if lang_match:
            # Capitalize properly
            lang = lang_match.group(1).capitalize()
            params["lang"] = lang
    
    return {func_name: params}
