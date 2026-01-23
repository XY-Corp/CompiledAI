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
        param_enum = param_info.get("enum", [])
        
        if param_type == "float" or param_type == "number":
            # Extract float/decimal numbers from query
            # Pattern: "0.3", "0.75", "1.0", etc.
            float_matches = re.findall(r'\b(\d+\.\d+|\d+)\b', query)
            if float_matches:
                # Take the first float found (usually the allele frequency)
                params[param_name] = float(float_matches[0])
        
        elif param_type == "integer":
            # Extract integers
            int_matches = re.findall(r'\b(\d+)\b', query)
            if int_matches:
                params[param_name] = int(int_matches[0])
        
        elif param_type == "string":
            if param_enum:
                # Look for enum values in the query (case-insensitive)
                for enum_val in param_enum:
                    # Match the enum value as a word boundary
                    if re.search(r'\b' + re.escape(enum_val) + r'\b', query, re.IGNORECASE):
                        params[param_name] = enum_val
                        break
                    # Also check for patterns like "AA genotype" or "genotype of AA"
                    pattern = rf'(?:genotype\s+(?:of\s+)?|frequency\s+of\s+){re.escape(enum_val)}\b|\b{re.escape(enum_val)}\s+genotype'
                    if re.search(pattern, query, re.IGNORECASE):
                        params[param_name] = enum_val
                        break
            else:
                # Generic string extraction - look for quoted strings or key patterns
                quoted = re.findall(r'"([^"]+)"', query)
                if quoted:
                    params[param_name] = quoted[0]
    
    return {func_name: params}
