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
    
    Uses regex and string parsing to extract values - no LLM calls needed.
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
                if len(data["question"][0]) > 0 and isinstance(data["question"][0][0], dict):
                    query = data["question"][0][0].get("content", str(prompt))
                else:
                    query = str(prompt)
            else:
                query = str(prompt)
        else:
            query = str(prompt)
    except (json.JSONDecodeError, TypeError):
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
    
    # Get target function details
    func = funcs[0]
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    required_params = func.get("parameters", {}).get("required", [])
    
    # Extract parameters based on schema
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        # For this specific function (get_event_date), extract event name
        if param_name == "event":
            # The query IS the event description - extract the event name
            # Common patterns: "When was X?", "What date was X?", "When did X happen?"
            event_patterns = [
                r"when\s+was\s+(?:the\s+)?(.+?)(?:\?|$)",
                r"what\s+(?:date|day)\s+was\s+(?:the\s+)?(.+?)(?:\?|$)",
                r"when\s+did\s+(?:the\s+)?(.+?)(?:\s+happen|\s+occur|\?|$)",
                r"date\s+of\s+(?:the\s+)?(.+?)(?:\?|$)",
            ]
            
            event_value = None
            for pattern in event_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    event_value = match.group(1).strip().rstrip("?")
                    break
            
            # Fallback: if no pattern matched, use the whole query minus question words
            if not event_value:
                # Remove common question starters
                event_value = re.sub(r"^(when|what|where|who|how)\s+(was|is|did|does|were|are)\s+(the\s+)?", "", query, flags=re.IGNORECASE)
                event_value = event_value.strip().rstrip("?")
            
            if event_value:
                params[param_name] = event_value
        
        elif param_name == "location":
            # Extract location if mentioned - look for "in [location]" or "at [location]"
            location_patterns = [
                r"(?:in|at)\s+([A-Z][a-zA-Z\s]+?)(?:\?|,|$)",
                r"(?:held\s+(?:in|at))\s+([A-Z][a-zA-Z\s]+?)(?:\?|,|$)",
            ]
            
            for pattern in location_patterns:
                match = re.search(pattern, query)
                if match:
                    params[param_name] = match.group(1).strip()
                    break
            # If location not found and not required, don't add it (use default)
    
    # Ensure required params are present
    for req_param in required_params:
        if req_param not in params:
            # If required param missing, try to extract from query as fallback
            if req_param == "event" and "event" not in params:
                # Use the query itself as the event name (cleaned up)
                cleaned = re.sub(r"^(when|what|where|who|how)\s+(was|is|did|does|were|are)\s+(the\s+)?", "", query, flags=re.IGNORECASE)
                params["event"] = cleaned.strip().rstrip("?")
    
    return {func_name: params}
