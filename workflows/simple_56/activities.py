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
    
    Uses regex and string matching to extract parameter values - no LLM calls needed.
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
    required_params = func.get("parameters", {}).get("required", [])
    
    # Extract parameters based on schema
    params = {}
    query_lower = query.lower()
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_type == "boolean":
            # Check for boolean indicators in query
            # Look for explicit mentions of description, details, etc.
            if "description" in param_name.lower() or "description" in param_desc:
                # Only set to true if explicitly requested
                if any(word in query_lower for word in ["description", "describe", "details", "detailed", "explain"]):
                    params[param_name] = True
                # Otherwise use default or skip (let default apply)
            else:
                # Generic boolean - check for yes/no/true/false
                if any(word in query_lower for word in ["yes", "true", "include", "with"]):
                    params[param_name] = True
                elif any(word in query_lower for word in ["no", "false", "without", "exclude"]):
                    params[param_name] = False
        
        elif param_type == "integer" or param_type == "number":
            # Extract numbers from query
            numbers = re.findall(r'\b\d+(?:\.\d+)?\b', query)
            if numbers:
                if param_type == "integer":
                    params[param_name] = int(float(numbers[0]))
                else:
                    params[param_name] = float(numbers[0])
        
        elif param_type == "string":
            # For string parameters, try to extract relevant value
            # Check if param relates to cell compartment, location, etc.
            if "compartment" in param_name.lower() or "compartment" in param_desc:
                # Extract cell compartment - look for common patterns
                # Pattern: "in the X" or "found in X" or "in X"
                compartment_patterns = [
                    r'(?:in|from|of)\s+(?:the\s+)?([a-zA-Z\s]+?)(?:\?|$|,|\.|!)',
                    r'(?:plasma membrane|cytoplasm|nucleus|mitochondria|endoplasmic reticulum|golgi|lysosome|ribosome|cell membrane)',
                ]
                
                # Try specific compartment names first
                compartments = [
                    "plasma membrane", "cell membrane", "cytoplasm", "nucleus", 
                    "mitochondria", "mitochondrion", "endoplasmic reticulum", 
                    "golgi apparatus", "golgi", "lysosome", "ribosome",
                    "cytoskeleton", "vacuole", "chloroplast", "peroxisome"
                ]
                
                found_compartment = None
                for comp in compartments:
                    if comp in query_lower:
                        found_compartment = comp
                        break
                
                if found_compartment:
                    params[param_name] = found_compartment
                else:
                    # Try regex pattern
                    match = re.search(r'(?:in|from|of)\s+(?:the\s+)?([a-zA-Z\s]+?)(?:\?|$|,|\.|!)', query, re.IGNORECASE)
                    if match:
                        extracted = match.group(1).strip()
                        # Clean up common trailing words
                        extracted = re.sub(r'\s+(are|is|can|do|does|have|has)$', '', extracted, flags=re.IGNORECASE)
                        if extracted:
                            params[param_name] = extracted
            else:
                # Generic string extraction - try to find quoted strings or key phrases
                quoted = re.findall(r'"([^"]+)"', query)
                if quoted:
                    params[param_name] = quoted[0]
    
    # Ensure required params are present
    for req_param in required_params:
        if req_param not in params:
            # Try harder to extract required params
            if "compartment" in req_param.lower():
                # Default extraction for compartment if not found
                match = re.search(r'(?:in|from|of)\s+(?:the\s+)?([a-zA-Z\s]+?)(?:\?|$)', query, re.IGNORECASE)
                if match:
                    params[req_param] = match.group(1).strip().rstrip('?')
    
    return {func_name: params}
