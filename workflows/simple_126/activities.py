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
    """Extract function call parameters from natural language query.
    
    Parses the user query to extract the function name and parameters
    based on the provided function schema. Returns format: {"func_name": {params}}.
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
    
    params = {}
    
    # Extract dataset_path - look for file paths
    if "dataset_path" in props:
        # Match Windows or Unix paths ending in common data extensions
        path_match = re.search(r'(?:path\s+)?([A-Za-z]:[/\\][^\s,]+\.\w+|/[^\s,]+\.\w+)', query, re.IGNORECASE)
        if path_match:
            params["dataset_path"] = path_match.group(1)
        else:
            # Try to find any path-like string
            path_match = re.search(r'([A-Za-z]:[/\\][^\s]+)', query)
            if path_match:
                params["dataset_path"] = path_match.group(1)
    
    # Extract dependent_variable - typically "predict X" or "to predict X"
    if "dependent_variable" in props:
        # Look for "predict <variable>" pattern
        dep_match = re.search(r'predict\s+(\w+)', query, re.IGNORECASE)
        if dep_match:
            params["dependent_variable"] = dep_match.group(1)
    
    # Extract independent_variables - look for "using X and Y variables" or similar
    if "independent_variables" in props:
        # Pattern: "using X and Y variables" or "using X and Y"
        ind_match = re.search(r'using\s+(.+?)\s+(?:variables?\s+)?to\s+predict', query, re.IGNORECASE)
        if ind_match:
            vars_text = ind_match.group(1)
            # Split by "and" or commas, clean up
            vars_list = re.split(r'\s+and\s+|\s*,\s*', vars_text)
            # Clean each variable name (remove extra words like "variables")
            cleaned_vars = []
            for v in vars_list:
                # Extract just the variable name (word characters, underscores, spaces for multi-word)
                v = v.strip()
                # Remove trailing "variables" or "variable"
                v = re.sub(r'\s*variables?\s*$', '', v, flags=re.IGNORECASE)
                # Replace spaces with underscores for variable names
                v = v.replace(' ', '_')
                if v:
                    cleaned_vars.append(v)
            params["independent_variables"] = cleaned_vars
    
    return {func_name: params}
