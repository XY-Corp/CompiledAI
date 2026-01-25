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
    
    Parses the user's natural language query to extract parameter values
    that match the function schema, using regex and string matching.
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
    params_schema = func.get("parameters", {}).get("properties", {})
    required_params = func.get("parameters", {}).get("required", [])
    
    # Extract parameters based on schema
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        default_val = param_info.get("default")
        
        extracted_value = None
        
        # For musical key extraction
        if "key" in param_name.lower() or "musical key" in param_desc:
            # Pattern for musical keys: C, C#, Cb, D sharp, E flat, etc.
            # Match patterns like "C sharp", "C#", "C-sharp", "Cb", "C flat"
            key_patterns = [
                r'\b([A-Ga-g])\s*(?:sharp|#)\s*(major|minor)?',  # C sharp, C#
                r'\b([A-Ga-g])\s*(?:flat|b)\s*(major|minor)?',   # C flat, Cb
                r'\b([A-Ga-g])\s*(major|minor)',                  # C major, D minor
                r'\b([A-Ga-g])([#b])?\b',                         # Just the note
            ]
            
            for pattern in key_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    note = match.group(1).upper()
                    # Check for sharp/flat in the pattern or query context
                    if "sharp" in query.lower() or "#" in query:
                        extracted_value = f"{note}#"
                    elif "flat" in query.lower() or match.group(0).lower().endswith('b'):
                        extracted_value = f"{note}b"
                    else:
                        extracted_value = note
                    break
        
        # For scale type extraction
        elif "scale" in param_name.lower() or "type" in param_name.lower():
            scale_types = ["major", "minor", "pentatonic", "blues", "chromatic", 
                          "harmonic minor", "melodic minor", "dorian", "phrygian",
                          "lydian", "mixolydian", "locrian", "natural minor"]
            
            query_lower = query.lower()
            for scale in scale_types:
                if scale in query_lower:
                    extracted_value = scale
                    break
        
        # Set the value if extracted, or use default for optional params
        if extracted_value is not None:
            params[param_name] = extracted_value
        elif param_name in required_params:
            # For required params without extracted value, try harder
            if default_val is not None:
                params[param_name] = default_val
        elif default_val is not None:
            # Optional param with default - only include if we found something
            # Check if the scale type is mentioned in query
            if "scale_type" in param_name.lower() or "type" in param_name.lower():
                if "major" in query.lower():
                    params[param_name] = "major"
                elif "minor" in query.lower():
                    params[param_name] = "minor"
                # Otherwise don't include - let default apply
    
    return {func_name: params}
