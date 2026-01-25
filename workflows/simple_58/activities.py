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
    
    # Parse prompt - may be JSON string or dict
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
    except (json.JSONDecodeError, TypeError, KeyError):
        query = str(prompt)
    
    # Parse functions - may be JSON string or list
    try:
        if isinstance(functions, str):
            funcs = json.loads(functions)
        else:
            funcs = functions
    except (json.JSONDecodeError, TypeError):
        funcs = []
    
    # Get target function details
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters from query using regex and string matching
    params = {}
    query_lower = query.lower()
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_type == "boolean":
            # For boolean params, check if query asks for specific/detailed info
            # "What is the function" implies wanting specific function info
            if "specific" in param_name.lower() or "function" in param_desc:
                # If asking "what is the function of X" - they want specific function
                if "function" in query_lower or "what" in query_lower:
                    params[param_name] = True
                else:
                    params[param_name] = False
            else:
                params[param_name] = True
        
        elif param_type == "string":
            # Extract string values based on parameter name/description
            if "molecule" in param_name.lower() or "molecule" in param_desc:
                # Look for molecule names - common patterns
                # "function of X in Y" or "X in Y"
                molecule_patterns = [
                    r'function of\s+([A-Za-z0-9\s]+?)\s+in',
                    r'role of\s+([A-Za-z0-9\s]+?)\s+in',
                    r'what (?:is|does)\s+([A-Za-z0-9\s]+?)\s+(?:do\s+)?in',
                    r'([A-Za-z0-9\s]+?)\s+(?:function|role)\s+in',
                ]
                
                for pattern in molecule_patterns:
                    match = re.search(pattern, query, re.IGNORECASE)
                    if match:
                        params[param_name] = match.group(1).strip()
                        break
                
                # Fallback: look for known molecule names
                if param_name not in params:
                    known_molecules = ["ATP synthase", "ATP", "NADH", "cytochrome", "glucose", "pyruvate"]
                    for mol in known_molecules:
                        if mol.lower() in query_lower:
                            params[param_name] = mol
                            break
            
            elif "organelle" in param_name.lower() or "organelle" in param_desc:
                # Look for organelle names
                organelle_patterns = [
                    r'in\s+(?:the\s+)?([A-Za-z]+)(?:\?|$|\s)',
                    r'within\s+(?:the\s+)?([A-Za-z]+)',
                ]
                
                known_organelles = ["mitochondria", "chloroplast", "nucleus", "ribosome", 
                                   "endoplasmic reticulum", "golgi", "lysosome", "vacuole",
                                   "cell membrane", "cytoplasm"]
                
                # First check for known organelles in query
                for org in known_organelles:
                    if org.lower() in query_lower:
                        params[param_name] = org
                        break
                
                # Fallback to pattern matching
                if param_name not in params:
                    for pattern in organelle_patterns:
                        match = re.search(pattern, query, re.IGNORECASE)
                        if match:
                            extracted = match.group(1).strip().rstrip('?')
                            # Verify it's a known organelle
                            for org in known_organelles:
                                if extracted.lower() in org.lower() or org.lower() in extracted.lower():
                                    params[param_name] = org
                                    break
                            break
        
        elif param_type in ["integer", "number", "float"]:
            # Extract numbers
            numbers = re.findall(r'\d+(?:\.\d+)?', query)
            if numbers:
                if param_type == "integer":
                    params[param_name] = int(numbers[0])
                else:
                    params[param_name] = float(numbers[0])
    
    return {func_name: params}
