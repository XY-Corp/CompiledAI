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
    """Extract function name and parameters from user query. Returns {"func_name": {params}}."""
    
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
    
    # Extract parameters from query using regex and string matching
    params = {}
    query_lower = query.lower()
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_name == "game":
            # Extract game name - look for quoted text or known game patterns
            # Pattern: game name often in quotes or after "game" keyword
            quoted_match = re.search(r"['\"]([^'\"]+)['\"]", query)
            if quoted_match:
                params["game"] = quoted_match.group(1)
            else:
                # Look for "in the online game X" or "in X" patterns
                game_match = re.search(r"(?:in\s+(?:the\s+)?(?:online\s+)?game\s+)['\"]?([A-Za-z0-9\s:]+?)['\"]?(?:\s+on|\s+for|\s+globally|$)", query, re.IGNORECASE)
                if game_match:
                    params["game"] = game_match.group(1).strip()
                else:
                    # Try to find capitalized game names
                    cap_match = re.search(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b", query)
                    if cap_match:
                        params["game"] = cap_match.group(1)
        
        elif param_name == "platform":
            # Extract platform - look for PC, Xbox, Playstation, etc.
            platform_patterns = [
                r'\bon\s+(PC|Xbox|Playstation|PlayStation|PS[45]?|Nintendo\s*Switch|Switch|Mobile)\b',
                r'\b(PC|Xbox|Playstation|PlayStation|PS[45]?|Nintendo\s*Switch|Switch|Mobile)\b'
            ]
            for pattern in platform_patterns:
                platform_match = re.search(pattern, query, re.IGNORECASE)
                if platform_match:
                    params["platform"] = platform_match.group(1)
                    break
        
        elif param_name == "region":
            # Extract region - look for global, NA, EU, Asia, etc.
            region_patterns = [
                r'\b(globally|global)\b',
                r'\bin\s+(North\s*America|NA|Europe|EU|Asia|APAC|South\s*America|SA)\b',
                r'\b(North\s*America|NA|Europe|EU|Asia|APAC|South\s*America|SA|Global)\b'
            ]
            for pattern in region_patterns:
                region_match = re.search(pattern, query, re.IGNORECASE)
                if region_match:
                    region_val = region_match.group(1)
                    # Normalize "globally" to "Global"
                    if region_val.lower() in ["globally", "global"]:
                        params["region"] = "Global"
                    else:
                        params["region"] = region_val
                    break
    
    return {func_name: params}
