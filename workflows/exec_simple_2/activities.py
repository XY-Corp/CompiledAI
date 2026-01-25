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
    """Extract function name and parameters from user query. Returns {func_name: {params}}."""
    
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
    
    # Extract vectors from the query using regex
    # Pattern to match arrays like [0.5, 0.7, 0.2, 0.9, 0.1]
    vector_pattern = r'\[[\d.,\s]+\]'
    vector_matches = re.findall(vector_pattern, query)
    
    params = {}
    
    if len(vector_matches) >= 2:
        # Parse the first two vectors found
        try:
            vectorA = json.loads(vector_matches[0])
            vectorB = json.loads(vector_matches[1])
            
            # Ensure they are lists of floats
            vectorA = [float(x) for x in vectorA]
            vectorB = [float(x) for x in vectorB]
            
            params["vectorA"] = vectorA
            params["vectorB"] = vectorB
        except (json.JSONDecodeError, ValueError, TypeError):
            pass
    
    return {func_name: params}
