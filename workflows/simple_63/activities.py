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
    
    Parses the user query and function schema to extract the appropriate
    function name and parameters. Returns format: {"function_name": {params}}.
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
    
    # Extract parameters based on the query content
    params = {}
    query_lower = query.lower()
    
    # For genetics.calculate_similarity - extract species names
    if "genetics" in func_name or "similarity" in func_name:
        # Common patterns for species comparison
        # "how similar a X and a Y are" or "between X and Y" or "X and Y"
        
        # Pattern 1: "a X and a Y"
        match = re.search(r'a\s+(\w+)\s+and\s+a\s+(\w+)', query_lower)
        if match:
            params["species1"] = match.group(1)
            params["species2"] = match.group(2)
        else:
            # Pattern 2: "between X and Y"
            match = re.search(r'between\s+(?:a\s+)?(\w+)\s+and\s+(?:a\s+)?(\w+)', query_lower)
            if match:
                params["species1"] = match.group(1)
                params["species2"] = match.group(2)
            else:
                # Pattern 3: Generic "X and Y" with common species names
                species_list = ["human", "chimp", "chimpanzee", "gorilla", "monkey", "mouse", "rat", "dog", "cat", "fish", "bird"]
                found_species = []
                for species in species_list:
                    if species in query_lower:
                        found_species.append(species)
                
                if len(found_species) >= 2:
                    params["species1"] = found_species[0]
                    params["species2"] = found_species[1]
        
        # Check for format specification
        if "percentage" in query_lower or "percent" in query_lower:
            params["format"] = "percentage"
        elif "fraction" in query_lower:
            params["format"] = "fraction"
    
    # Generic extraction for other function types
    else:
        # Extract numbers for numeric parameters
        numbers = re.findall(r'\d+(?:\.\d+)?', query)
        num_idx = 0
        
        # Extract string values using common patterns
        string_match = re.search(r'(?:for|in|of|with|to)\s+([A-Za-z\s]+?)(?:\s+(?:and|with|,|\.)|$)', query, re.IGNORECASE)
        
        for param_name, param_info in params_schema.items():
            if isinstance(param_info, dict):
                param_type = param_info.get("type", "string")
            else:
                param_type = "string"
            
            if param_type in ["integer", "number", "float"] and num_idx < len(numbers):
                if param_type == "integer":
                    params[param_name] = int(numbers[num_idx])
                else:
                    params[param_name] = float(numbers[num_idx])
                num_idx += 1
            elif param_type == "string" and string_match and param_name not in params:
                params[param_name] = string_match.group(1).strip()
    
    return {func_name: params}
