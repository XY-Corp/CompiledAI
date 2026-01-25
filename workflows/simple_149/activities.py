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
    """Extract function call from user query and return as {func_name: {params}}.
    
    Parses the prompt to extract the user's query, identifies the target function,
    and extracts parameter values using regex and string matching.
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
    
    # Get target function details
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters based on schema
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        
        if param_type == "array":
            items_type = param_info.get("items", {}).get("type", "string")
            
            if items_type == "string":
                # For company names, stock symbols, etc. - extract proper nouns/entities
                # Common patterns: "X and Y", "X, Y, and Z", etc.
                
                # Look for company names (capitalized words or known patterns)
                # Pattern 1: Extract words after "of" until end or punctuation
                of_match = re.search(r'\bof\s+(.+?)(?:\?|$)', query, re.IGNORECASE)
                if of_match:
                    entities_text = of_match.group(1).strip()
                    # Split by "and" or commas
                    entities = re.split(r'\s+and\s+|,\s*', entities_text, flags=re.IGNORECASE)
                    entities = [e.strip() for e in entities if e.strip()]
                    params[param_name] = entities
                else:
                    # Fallback: extract capitalized words that look like company names
                    # Exclude common words
                    exclude_words = {'what', 'the', 'current', 'stock', 'price', 'get', 'find', 'show', 'me', 'please', 'i', 'want', 'to', 'know'}
                    words = re.findall(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b', query)
                    entities = [w for w in words if w.lower() not in exclude_words]
                    if entities:
                        params[param_name] = entities
                    else:
                        params[param_name] = []
            
            elif items_type in ["integer", "number", "float"]:
                # Extract all numbers
                numbers = re.findall(r'-?\d+(?:\.\d+)?', query)
                if items_type == "integer":
                    params[param_name] = [int(float(n)) for n in numbers]
                else:
                    params[param_name] = [float(n) for n in numbers]
        
        elif param_type == "integer":
            numbers = re.findall(r'-?\d+', query)
            if numbers:
                params[param_name] = int(numbers[0])
        
        elif param_type in ["number", "float"]:
            numbers = re.findall(r'-?\d+(?:\.\d+)?', query)
            if numbers:
                params[param_name] = float(numbers[0])
        
        elif param_type == "string":
            # Try to extract relevant string value based on param name hints
            # This is a simple heuristic - extract text after common prepositions
            match = re.search(r'(?:for|of|about|named?|called?)\s+["\']?([^"\'?,]+)["\']?', query, re.IGNORECASE)
            if match:
                params[param_name] = match.group(1).strip()
    
    return {func_name: params}
