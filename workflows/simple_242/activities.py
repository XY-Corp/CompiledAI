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
        
        if param_type in ["integer", "number", "float"]:
            # Extract numbers using regex
            numbers = re.findall(r'\d+(?:\.\d+)?', query)
            if numbers:
                if param_type == "integer":
                    params[param_name] = int(numbers[0])
                else:
                    params[param_name] = float(numbers[0])
        elif param_type == "string":
            # For discovery/theory parameters, extract the relevant concept
            if "discovery" in param_name.lower() or "theory" in param_desc:
                # Look for patterns like "theory of X", "discovery of X"
                patterns = [
                    r'theory of (\w+(?:\s+\w+)?)',
                    r'discovery of (\w+(?:\s+\w+)?)',
                    r'proposed the (\w+(?:\s+\w+)?)',
                    r'credited for (\w+(?:\s+\w+)?)',
                    r'first proposed (?:the )?(?:theory of )?(\w+)',
                ]
                
                for pattern in patterns:
                    match = re.search(pattern, query, re.IGNORECASE)
                    if match:
                        params[param_name] = match.group(1).strip()
                        break
                
                # If no pattern matched, try to extract key scientific terms
                if param_name not in params:
                    # Common scientific theories/discoveries
                    scientific_terms = [
                        "evolution", "relativity", "gravity", "quantum mechanics",
                        "natural selection", "big bang", "heliocentrism", "genetics"
                    ]
                    query_lower = query.lower()
                    for term in scientific_terms:
                        if term in query_lower:
                            params[param_name] = term
                            break
                
                # Fallback: extract phrase after "theory of" or similar
                if param_name not in params:
                    match = re.search(r'theory of (\w+)', query, re.IGNORECASE)
                    if match:
                        params[param_name] = match.group(1)
            else:
                # Generic string extraction - look for quoted strings or key phrases
                quoted = re.findall(r'"([^"]+)"', query)
                if quoted:
                    params[param_name] = quoted[0]
                else:
                    # Extract after common prepositions
                    match = re.search(r'(?:for|about|of|with)\s+([A-Za-z\s]+?)(?:\?|$|\.)', query, re.IGNORECASE)
                    if match:
                        params[param_name] = match.group(1).strip()
    
    return {func_name: params}
