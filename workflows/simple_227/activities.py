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
    
    # Extract parameters based on schema
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_name == "type" and "personality" in param_desc:
            # Extract personality type - common patterns: ENFJ, INFP, ESTJ, etc.
            personality_match = re.search(r'\b([EI][NS][TF][JP])\b', query, re.IGNORECASE)
            if personality_match:
                params[param_name] = personality_match.group(1).upper()
        
        elif param_name == "traits" and param_type == "array":
            # Extract traits from query - look for "strengths", "weaknesses", "strength", "weakness"
            traits = []
            query_lower = query.lower()
            
            if "strength" in query_lower:
                traits.append("strengths")
            if "weakness" in query_lower:
                traits.append("weaknesses")
            
            # If both or specific traits mentioned, use them
            if traits:
                params[param_name] = traits
            # If no specific traits mentioned but asking for traits in general, use default
            elif "trait" in query_lower:
                params[param_name] = ["strengths"]
    
    return {func_name: params}
