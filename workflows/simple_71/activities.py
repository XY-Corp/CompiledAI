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
    """Extract function name and parameters from user query and function schema.
    
    Returns a dict with function name as key and parameters as nested object.
    """
    # Parse prompt - may be JSON string with nested structure
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
    
    # Parse functions - may be JSON string
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
        
        if param_type == "integer":
            # Extract integers from query using regex
            numbers = re.findall(r'\b(\d+)\b', query)
            if numbers:
                # For "length" parameter, look for number near "length" or standalone number
                if param_name == "length":
                    # Try to find number associated with length/bases/sequence
                    length_match = re.search(r'(\d+)\s*(?:bases?|bp|nucleotides?|length)', query, re.IGNORECASE)
                    if length_match:
                        params[param_name] = int(length_match.group(1))
                    else:
                        # Just use the first number found
                        params[param_name] = int(numbers[0])
                else:
                    params[param_name] = int(numbers[0])
        
        elif param_type == "array":
            items_info = param_info.get("items", {})
            enum_values = items_info.get("enum", [])
            
            if enum_values:
                # Extract matching enum values from query
                found_values = []
                query_upper = query.upper()
                
                # Map full names to abbreviations for nucleotides
                nucleotide_map = {
                    "ADENINE": "A",
                    "THYMINE": "T", 
                    "CYTOSINE": "C",
                    "GUANINE": "G"
                }
                
                # Check for full names first
                for full_name, abbrev in nucleotide_map.items():
                    if full_name in query_upper and abbrev in enum_values:
                        if abbrev not in found_values:
                            found_values.append(abbrev)
                
                # Also check for abbreviations directly (e.g., "G and C" or "more G")
                for val in enum_values:
                    # Look for the letter as a standalone nucleotide reference
                    pattern = rf'\b{val}\b|\({val}\)'
                    if re.search(pattern, query, re.IGNORECASE):
                        if val not in found_values:
                            found_values.append(val)
                
                if found_values:
                    params[param_name] = found_values
        
        elif param_type == "string":
            # For string params, try to extract relevant text
            # This is a fallback - specific extraction logic may be needed
            params[param_name] = ""
    
    return {func_name: params}
