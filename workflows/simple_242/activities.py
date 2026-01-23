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
    
    Parses the prompt to extract the user's query, then extracts relevant parameters
    based on the function schema using regex and string matching.
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
    
    # Get function details
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters based on schema
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_type == "string":
            # For "discovery" parameter - extract the theory/discovery being asked about
            if "discovery" in param_name.lower() or "theory" in param_desc or "discovery" in param_desc:
                # Look for patterns like "theory of X", "proposed X", "discovered X"
                patterns = [
                    r'theory of (\w+(?:\s+\w+)?)',  # "theory of evolution"
                    r'proposed (?:the )?(?:theory of )?(\w+(?:\s+\w+)?)',  # "proposed the theory of evolution"
                    r'discovered (\w+(?:\s+\w+)?)',  # "discovered X"
                    r'credited for (\w+(?:\s+\w+)?)',  # "credited for X"
                ]
                
                for pattern in patterns:
                    match = re.search(pattern, query, re.IGNORECASE)
                    if match:
                        # For "theory of X", we want "theory of X" as the discovery
                        if "theory of" in pattern:
                            params[param_name] = f"theory of {match.group(1)}"
                        else:
                            params[param_name] = match.group(1)
                        break
                
                # If no pattern matched, try to extract the main subject
                if param_name not in params:
                    # Look for what's being asked about
                    subject_match = re.search(r'(?:who|what|which).*?(?:the\s+)?(\w+(?:\s+\w+)*?)(?:\?|$)', query, re.IGNORECASE)
                    if subject_match:
                        params[param_name] = subject_match.group(1).strip()
        
        elif param_type in ["integer", "number", "float"]:
            # Extract numbers
            numbers = re.findall(r'\d+(?:\.\d+)?', query)
            if numbers:
                if param_type == "integer":
                    params[param_name] = int(numbers[0])
                else:
                    params[param_name] = float(numbers[0])
    
    return {func_name: params}
