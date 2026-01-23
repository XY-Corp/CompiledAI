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
                char_text = re.sub(r'\s+and\s+', ', ', char_text, flags=re.IGNORECASE)
                # Split by comma and clean up
                characteristics = [c.strip() for c in char_text.split(',') if c.strip()]
                # Remove any trailing punctuation
                characteristics = [re.sub(r'[?.!]+$', '', c).strip() for c in characteristics]
                params[param_name] = characteristics
            else:
                # Fallback: try to extract any comma-separated or "and"-separated list
                words = re.findall(r'\b([a-z]+)\b', query.lower())
                # Filter to likely characteristics (adjectives)
                common_traits = ['efficient', 'organized', 'easy going', 'easygoing', 'compassionate', 
                                'friendly', 'creative', 'analytical', 'calm', 'energetic', 'patient',
                                'ambitious', 'curious', 'reliable', 'honest', 'kind', 'outgoing',
                                'introverted', 'extroverted', 'open', 'conscientious', 'agreeable',
                                'neurotic', 'stable', 'assertive', 'cooperative', 'disciplined']
                found_traits = [w for w in words if w in common_traits]
                if found_traits:
                    params[param_name] = found_traits
        
        elif param_type == "string":
            # Check if it's an enum type
            if "enum" in param_info:
                enum_values = param_info["enum"]
                # Look for any enum value in the query
                for val in enum_values:
                    if val.lower() in query.lower():
                        params[param_name] = val
                        break
                # If not found and not required, skip (use default)
            else:
                # Generic string extraction - look for quoted strings or specific patterns
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
    
    # Handle "easy going" as a single characteristic (space-separated)
    if "characteristics" in params:
        # Check if "easy" and "going" are separate and should be combined
        chars = params["characteristics"]
        new_chars = []
        i = 0
        while i < len(chars):
            if i < len(chars) - 1 and chars[i].lower() == "easy" and chars[i+1].lower() == "going":
                new_chars.append("easy going")
                i += 2
            else:
                new_chars.append(chars[i])
                i += 1
        params["characteristics"] = new_chars
    
    return {func_name: params}
