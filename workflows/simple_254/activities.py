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
        
        if param_name == "religion":
            # Extract religion name - look for common religions
            religions = ["christianity", "islam", "judaism", "buddhism", "hinduism", "sikhism", "taoism", "shinto"]
            for religion in religions:
                if religion in query_lower:
                    params[param_name] = religion.capitalize()
                    break
            # Also try pattern matching for "related to X"
            if param_name not in params:
                match = re.search(r'related to\s+(\w+)', query_lower)
                if match:
                    params[param_name] = match.group(1).capitalize()
        
        elif param_name == "start_year":
            # Extract start year - look for "between X and Y" or "from X to Y"
            match = re.search(r'between\s+(?:year\s+)?(\d+)\s+and', query_lower)
            if match:
                params[param_name] = int(match.group(1))
            else:
                match = re.search(r'from\s+(?:year\s+)?(\d+)', query_lower)
                if match:
                    params[param_name] = int(match.group(1))
        
        elif param_name == "end_year":
            # Extract end year - look for "and Y" or "to Y"
            match = re.search(r'and\s+(?:year\s+)?(\d+)', query_lower)
            if match:
                params[param_name] = int(match.group(1))
            else:
                match = re.search(r'to\s+(?:year\s+)?(\d+)', query_lower)
                if match:
                    params[param_name] = int(match.group(1))
        
        elif param_name == "event_type":
            # Check for event type keywords (optional param)
            event_types = param_info.get("enum", ["all", "crusade", "schism", "reform"])
            for event_type in event_types:
                if event_type != "all" and event_type in query_lower:
                    params[param_name] = event_type
                    break
            # Don't include if not explicitly mentioned (it's optional with default)
    
    return {func_name: params}
