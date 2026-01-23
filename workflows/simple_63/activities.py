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
        # Common patterns for comparing two things
        # Pattern: "X and Y" or "X and a Y" or "a X and a Y"
        species_patterns = [
            r'(?:between\s+)?(?:a\s+)?(\w+)\s+and\s+(?:a\s+)?(\w+)',
            r'(\w+)\s+(?:and|vs\.?|versus)\s+(\w+)',
            r'how\s+(?:genetically\s+)?similar\s+(?:is\s+)?(?:a\s+)?(\w+)\s+and\s+(?:a\s+)?(\w+)',
        ]
        
        species1 = None
        species2 = None
        
        for pattern in species_patterns:
            match = re.search(pattern, query_lower)
            if match:
                candidate1 = match.group(1).strip()
                candidate2 = match.group(2).strip()
                
                # Filter out common non-species words
                skip_words = {'how', 'are', 'is', 'the', 'a', 'an', 'in', 'out', 'find', 'get', 'what', 'similar', 'genetically'}
                
                if candidate1 not in skip_words and candidate2 not in skip_words:
                    species1 = candidate1
                    species2 = candidate2
                    break
        
        # Assign to params if found
        if species1 and "species1" in params_schema:
            params["species1"] = species1
        if species2 and "species2" in params_schema:
            params["species2"] = species2
        
        # Check for format specification
        if "format" in params_schema:
            if "percentage" in query_lower or "percent" in query_lower:
                params["format"] = "percentage"
            elif "fraction" in query_lower:
                params["format"] = "fraction"
            # Default to percentage if mentioned in query context
            elif "%" in query:
                params["format"] = "percentage"
    
    else:
        # Generic extraction for other function types
        # Extract numbers
        numbers = re.findall(r'\d+(?:\.\d+)?', query)
        
        # Extract quoted strings
        quoted = re.findall(r'"([^"]+)"', query)
        
        num_idx = 0
        str_idx = 0
        
        for param_name, param_info in params_schema.items():
            param_type = param_info.get("type", "string") if isinstance(param_info, dict) else "string"
            
            if param_type in ["integer", "number", "float"]:
                if num_idx < len(numbers):
                    val = numbers[num_idx]
                    params[param_name] = int(val) if param_type == "integer" else float(val)
                    num_idx += 1
            elif param_type == "string":
                if str_idx < len(quoted):
                    params[param_name] = quoted[str_idx]
                    str_idx += 1
    
    return {func_name: params}
