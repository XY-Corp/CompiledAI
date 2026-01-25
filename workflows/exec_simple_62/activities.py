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
    """Extract function name and parameters from user query for matrix multiplication."""
    
    # Parse prompt (may be JSON string)
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
        else:
            data = prompt
        
        # Extract user query from nested structure
        if "question" in data and isinstance(data["question"], list):
            if len(data["question"]) > 0 and isinstance(data["question"][0], list):
                query = data["question"][0][0].get("content", str(prompt))
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
    
    # Extract matrices using regex
    # Pattern to match matrix notation like [[1, 2], [3, 4]]
    matrix_pattern = r'\[\s*\[[\d\s,\-\.]+\](?:\s*,\s*\[[\d\s,\-\.]+\])*\s*\]'
    matrices = re.findall(matrix_pattern, query)
    
    params = {}
    
    if len(matrices) >= 2:
        # Parse the first two matrices found
        try:
            matA = json.loads(matrices[0].replace(' ', ''))
            matB = json.loads(matrices[1].replace(' ', ''))
            params["matA"] = matA
            params["matB"] = matB
        except json.JSONDecodeError:
            # Try more lenient parsing
            pass
    
    # If regex didn't work, try to find matrices in a different way
    if not params:
        # Look for patterns like "first one is [[...]]" and "second is [[...]]"
        first_match = re.search(r'first\s+(?:one\s+)?(?:is\s+)?(\[\[[\d\s,\-\.]+\](?:\s*,\s*\[[\d\s,\-\.]+\])*\])', query, re.IGNORECASE)
        second_match = re.search(r'second\s+(?:one\s+)?(?:is\s+)?(\[\[[\d\s,\-\.]+\](?:\s*,\s*\[[\d\s,\-\.]+\])*\])', query, re.IGNORECASE)
        
        if first_match and second_match:
            try:
                params["matA"] = json.loads(first_match.group(1).replace(' ', ''))
                params["matB"] = json.loads(second_match.group(1).replace(' ', ''))
            except json.JSONDecodeError:
                pass
    
    return {func_name: params}
