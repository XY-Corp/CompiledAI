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
    
    Uses regex and string matching to extract values - no LLM calls needed.
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
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters from query using regex and string matching
    params = {}
    query_lower = query.lower()
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        # Location extraction patterns
        if param_name == "location" or "city" in param_desc or "location" in param_desc:
            # Pattern: "near X", "in X", "at X", "around X"
            location_patterns = [
                r'near\s+([A-Za-z\s]+?)(?:\s+that|\s+which|\s+made|\s+from|,|$)',
                r'in\s+([A-Za-z\s]+?)(?:\s+that|\s+which|\s+made|\s+from|,|$)',
                r'at\s+([A-Za-z\s]+?)(?:\s+that|\s+which|\s+made|\s+from|,|$)',
                r'around\s+([A-Za-z\s]+?)(?:\s+that|\s+which|\s+made|\s+from|,|$)',
            ]
            for pattern in location_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    params[param_name] = match.group(1).strip()
                    break
        
        # Time frame extraction patterns
        elif param_name == "time_frame" or "time" in param_desc or "frame" in param_desc or "period" in param_desc:
            # Pattern: "in the Xth century", "from X to Y", "during X"
            time_patterns = [
                r'(\d+(?:st|nd|rd|th)\s+century)',
                r'((?:19|20|21)\d{2}s?)',
                r'from\s+(\d+)\s+to\s+(\d+)',
                r'during\s+(?:the\s+)?([A-Za-z0-9\s]+?)(?:\.|,|$)',
            ]
            for pattern in time_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    if match.lastindex and match.lastindex > 1:
                        # Range pattern like "from X to Y"
                        params[param_name] = f"{match.group(1)} to {match.group(2)}"
                    else:
                        params[param_name] = match.group(1).strip()
                    break
        
        # Material extraction (optional parameter)
        elif param_name == "material" or "material" in param_desc:
            # Pattern: "made of X", "X sculptures", common materials
            material_patterns = [
                r'made\s+(?:of|from)\s+([A-Za-z]+)',
                r'(bronze|marble|stone|wood|metal|glass|ceramic|clay|iron|steel|copper)\s+sculptures?',
                r'sculptures?\s+(?:made\s+)?(?:of|from)\s+([A-Za-z]+)',
            ]
            for pattern in material_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    params[param_name] = match.group(1).strip().lower()
                    break
            # Don't add material if not found (it's optional with default 'all')
    
    return {func_name: params}
