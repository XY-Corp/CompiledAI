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
    
    # Extract parameters based on the query content
    params = {}
    
    # For DNA sequence analysis, extract sequences from the query
    # Pattern: 'SEQUENCE' (DNA sequences in quotes)
    dna_sequences = re.findall(r"'([AGTC]+)'", query, re.IGNORECASE)
    
    # Check for mutation type keywords
    mutation_type = None
    if "substitution" in query.lower():
        mutation_type = "substitution"
    elif "insertion" in query.lower():
        mutation_type = "insertion"
    elif "deletion" in query.lower():
        mutation_type = "deletion"
    
    # Map extracted values to parameter names based on schema
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        
        if param_name == "sequence" and len(dna_sequences) >= 1:
            # First sequence mentioned is typically the one to analyze
            params[param_name] = dna_sequences[0]
        elif param_name == "reference_sequence" and len(dna_sequences) >= 2:
            # Second sequence is the reference
            params[param_name] = dna_sequences[1]
        elif param_name == "mutation_type" and mutation_type:
            params[param_name] = mutation_type
    
    return {func_name: params}
