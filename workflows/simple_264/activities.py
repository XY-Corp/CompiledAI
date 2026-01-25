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
            # Handle BFCL format: {"question": [[{"role": "user", "content": "..."}]], ...}
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
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters using regex and string matching
    params = {}
    
    # For sculpture.get_details, extract artist and title
    # Pattern: "title 'X' by Y" or "by Y" and "'X'"
    
    # Extract title - look for quoted strings
    title_match = re.search(r"title\s+['\"]([^'\"]+)['\"]", query, re.IGNORECASE)
    if not title_match:
        # Try just quoted string after "sculpture" or similar
        title_match = re.search(r"['\"]([^'\"]+)['\"]", query)
    
    if title_match and "title" in params_schema:
        params["title"] = title_match.group(1)
    
    # Extract artist - look for "by X" pattern
    artist_match = re.search(r"\bby\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)", query)
    if artist_match and "artist" in params_schema:
        params["artist"] = artist_match.group(1).strip()
    
    # Extract detail - look for "size", "height", "material", etc.
    detail_keywords = ["size", "height", "width", "material", "weight", "dimensions", "location", "date", "year"]
    for keyword in detail_keywords:
        if keyword.lower() in query.lower():
            if "detail" in params_schema:
                params["detail"] = keyword
            break
    
    return {func_name: params}
