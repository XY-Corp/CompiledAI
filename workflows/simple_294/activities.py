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
    
    # Extract parameters from query using regex and string matching
    params = {}
    query_lower = query.lower()
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_name == "key":
            # Extract musical key - look for patterns like "in C key", "C key", "key of C"
            key_patterns = [
                r'in\s+([A-Ga-g][#b]?)\s+key',
                r'([A-Ga-g][#b]?)\s+key',
                r'key\s+(?:of\s+)?([A-Ga-g][#b]?)',
                r'in\s+(?:the\s+)?key\s+(?:of\s+)?([A-Ga-g][#b]?)',
            ]
            for pattern in key_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    params[param_name] = match.group(1).upper()
                    break
        
        elif param_name == "chords":
            # Extract number of chords - look for patterns like "four chords", "4 chords"
            # First try word numbers
            word_to_num = {
                'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
                'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10
            }
            
            # Pattern for word numbers before "chord"
            word_pattern = r'(\w+)\s+chords?'
            word_match = re.search(word_pattern, query_lower)
            if word_match:
                word = word_match.group(1)
                if word in word_to_num:
                    params[param_name] = word_to_num[word]
                elif word.isdigit():
                    params[param_name] = int(word)
            
            # Fallback: extract any number near "chord"
            if param_name not in params:
                num_pattern = r'(\d+)\s+chords?'
                num_match = re.search(num_pattern, query_lower)
                if num_match:
                    params[param_name] = int(num_match.group(1))
        
        elif param_name == "progression_type":
            # Extract progression type - look for "major", "minor", etc.
            progression_types = ['major', 'minor', 'diminished', 'augmented', 'dominant', 'jazz', 'blues', 'pop']
            for prog_type in progression_types:
                if prog_type in query_lower:
                    # Make sure it's not part of another word
                    pattern = r'\b' + prog_type + r'\b'
                    if re.search(pattern, query_lower):
                        params[param_name] = prog_type
                        break
    
    return {func_name: params}
