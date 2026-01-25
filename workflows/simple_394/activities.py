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
    
    Uses regex and string parsing to extract location parameters from natural language queries.
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
    props = func.get("parameters", {}).get("properties", {})
    
    # Extract location parameters using regex patterns
    params = {}
    
    # Pattern for "from X to Y" format
    from_to_match = re.search(
        r'from\s+(?:the\s+)?(.+?)\s+to\s+(?:the\s+)?(.+?)(?:\s*$|\s+(?:by|via|using|with))',
        query,
        re.IGNORECASE
    )
    
    if from_to_match:
        start_loc = from_to_match.group(1).strip()
        end_loc = from_to_match.group(2).strip()
    else:
        # Alternative pattern: "between X and Y"
        between_match = re.search(
            r'between\s+(?:the\s+)?(.+?)\s+and\s+(?:the\s+)?(.+?)(?:\s*$|\s+(?:by|via|using|with))',
            query,
            re.IGNORECASE
        )
        if between_match:
            start_loc = between_match.group(1).strip()
            end_loc = between_match.group(2).strip()
        else:
            # Fallback: try to find location-like phrases
            # Look for proper nouns (capitalized words/phrases)
            locations = re.findall(r'(?:the\s+)?([A-Z][a-zA-Z\s]+(?:Tower|Museum|Station|Airport|Center|Centre|Park|Square|Bridge|Building|Palace|Castle|Cathedral|Church|Hotel|Restaurant|Mall|Market|Beach|Mountain|Lake|River|Street|Avenue|Boulevard|Road|Highway))', query)
            if len(locations) >= 2:
                start_loc = locations[0].strip()
                end_loc = locations[1].strip()
            else:
                start_loc = ""
                end_loc = ""
    
    # Assign to parameter names from schema
    if "start_location" in props:
        params["start_location"] = start_loc
    if "end_location" in props:
        params["end_location"] = end_loc
    
    # Check for traffic parameter (optional)
    if "traffic" in props:
        # Only include if explicitly mentioned
        traffic_match = re.search(r'\b(with\s+traffic|current\s+traffic|traffic\s+conditions?|consider\s+traffic)\b', query, re.IGNORECASE)
        if traffic_match:
            params["traffic"] = True
    
    return {func_name: params}
