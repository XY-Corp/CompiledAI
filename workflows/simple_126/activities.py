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
        path_patterns = [
            r'(?:path|file|dataset)\s+(?:is\s+)?([A-Za-z]:[/\\][^\s,]+\.\w+)',  # Windows path with drive letter
            r'(?:in\s+path|at\s+path|path)\s+([A-Za-z]:[/\\][^\s,]+\.\w+)',  # "in path C:/..."
            r'([A-Za-z]:[/\\][^\s,]+\.csv)',  # Direct Windows CSV path
            r'(/[^\s,]+\.csv)',  # Unix path
        ]
        for pattern in path_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                params["dataset_path"] = match.group(1)
                break
    
    # Extract independent_variables - look for variable names used as predictors
    if "independent_variables" in props:
        # Look for patterns like "using X and Y variables" or "X and Y to predict"
        # Common patterns: "using A and B variables", "A and B to predict", "variables A and B"
        var_patterns = [
            r'using\s+([a-z_]+(?:\s+and\s+[a-z_]+)*)\s+(?:variables?\s+)?to\s+predict',
            r'using\s+([a-z_]+)\s+and\s+([a-z_]+)\s+variables?\s+to\s+predict',
            r'(?:independent\s+)?variables?\s+([a-z_]+(?:\s+and\s+[a-z_]+)*)',
        ]
        
        independent_vars = []
        
        # Try pattern: "using X and Y variables to predict"
        match = re.search(r'using\s+([a-z_\s]+)\s+variables?\s+to\s+predict', query, re.IGNORECASE)
        if match:
            vars_text = match.group(1)
            # Split by "and" to get individual variables
            vars_list = re.split(r'\s+and\s+', vars_text, flags=re.IGNORECASE)
            independent_vars = [v.strip() for v in vars_list if v.strip()]
        
        if not independent_vars:
            # Try another pattern: look for words before "to predict"
            match = re.search(r'using\s+(.+?)\s+to\s+predict', query, re.IGNORECASE)
            if match:
                vars_text = match.group(1)
                # Remove "variables" word and split by "and"
                vars_text = re.sub(r'\s*variables?\s*', ' ', vars_text, flags=re.IGNORECASE)
                vars_list = re.split(r'\s+and\s+', vars_text, flags=re.IGNORECASE)
                independent_vars = [v.strip().replace(' ', '_') for v in vars_list if v.strip()]
        
        # Convert natural language to variable names (e.g., "engine size" -> "engine_size")
        cleaned_vars = []
        for var in independent_vars:
            # Replace spaces with underscores for multi-word variables
            cleaned_var = var.strip().replace(' ', '_').lower()
            if cleaned_var:
                cleaned_vars.append(cleaned_var)
        
        if cleaned_vars:
            params["independent_variables"] = cleaned_vars
    
    # Extract dependent_variable - look for what we're predicting
    if "dependent_variable" in props:
        # Look for patterns like "predict X" or "predicting X"
        dep_patterns = [
            r'to\s+predict\s+([a-z_]+)',
            r'predict(?:ing)?\s+([a-z_]+)',
            r'dependent\s+variable\s+([a-z_]+)',
        ]
        for pattern in dep_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                params["dependent_variable"] = match.group(1).strip().lower()
                break
    
    return {func_name: params}
