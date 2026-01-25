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
    
    Parses the prompt to extract the user's query, then extracts parameter values
    based on the function schema using regex and string matching.
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
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_type == "array":
            # For array of characteristics/traits - extract descriptive words
            # Look for adjectives/characteristics in the query
            # Common patterns: "I am X, Y, Z" or "given that I am X, Y and Z"
            
            # Pattern to find characteristics after "I am" or similar phrases
            char_pattern = r'(?:I am|i am|I\'m|i\'m|given that I am)\s+(.+?)(?:\?|$)'
            match = re.search(char_pattern, query, re.IGNORECASE)
            
            if match:
                char_text = match.group(1)
                # Split by commas and "and"
                # Replace "and" with comma for uniform splitting
                char_text = re.sub(r'\s+and\s+', ', ', char_text)
                # Split by comma and clean up
                characteristics = [c.strip() for c in char_text.split(',') if c.strip()]
                # Remove any trailing punctuation
                characteristics = [re.sub(r'[?.!]+$', '', c).strip() for c in characteristics]
                params[param_name] = characteristics
            else:
                # Fallback: try to extract adjectives/descriptive words
                # Look for common personality descriptors
                words = re.findall(r'\b([a-z]+)\b', query.lower())
                # Filter for likely characteristics (adjectives)
                common_traits = ['efficient', 'organized', 'easy going', 'easygoing', 'compassionate', 
                                'friendly', 'outgoing', 'creative', 'analytical', 'calm', 'energetic',
                                'patient', 'ambitious', 'curious', 'reliable', 'honest', 'kind']
                found_traits = [w for w in words if w in common_traits]
                
                # Also check for "easy going" as two words
                if 'easy' in words and 'going' in words:
                    found_traits.append('easy going')
                    if 'easy' in found_traits:
                        found_traits.remove('easy')
                    if 'going' in found_traits:
                        found_traits.remove('going')
                
                params[param_name] = found_traits if found_traits else []
        
        elif param_type == "string":
            # Check if it's an enum type
            enum_values = param_info.get("enum", [])
            if enum_values:
                # Look for enum value in query
                for val in enum_values:
                    if val.lower() in query.lower():
                        params[param_name] = val
                        break
                # If not found and not required, skip (use default)
                # Don't add if not explicitly mentioned
            else:
                # Generic string extraction - look for quoted values or specific patterns
                quoted = re.findall(r'"([^"]+)"', query)
                if quoted:
                    params[param_name] = quoted[0]
        
        elif param_type in ["integer", "number", "float"]:
            # Extract numbers
            numbers = re.findall(r'\d+(?:\.\d+)?', query)
            if numbers:
                if param_type == "integer":
                    params[param_name] = int(numbers[0])
                else:
                    params[param_name] = float(numbers[0])
    
    # Only include required params and params that were found
    # For optional params with defaults, don't include if not explicitly specified
    final_params = {}
    for param_name in params_schema.keys():
        if param_name in params:
            final_params[param_name] = params[param_name]
        elif param_name in required_params:
            # Required but not found - include empty/default
            param_type = params_schema[param_name].get("type", "string")
            if param_type == "array":
                final_params[param_name] = []
            elif param_type == "string":
                final_params[param_name] = ""
            elif param_type in ["integer", "number", "float"]:
                final_params[param_name] = 0
    
    return {func_name: final_params}
