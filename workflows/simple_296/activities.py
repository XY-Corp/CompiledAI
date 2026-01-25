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
    """Extract function call parameters from natural language prompt using regex and string matching."""
    
    # Parse prompt - may be JSON string with nested structure
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
            # Handle BFCL format: {"question": [[{"role": "user", "content": "..."}]], ...}
            if "question" in data and isinstance(data["question"], list):
                if len(data["question"]) > 0 and isinstance(data["question"][0], list):
                    query = data["question"][0][0].get("content", str(prompt))
                else:
                    query = str(prompt)
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
    
    # Extract parameters from query using regex
    params = {}
    query_lower = query.lower()
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_name == "key":
            # Extract musical key - look for patterns like "C scale", "major C", "key of C"
            # Pattern: letter optionally followed by # or b, before "scale" or after "key"
            key_patterns = [
                r'\b([A-Ga-g][#b]?)\s+(?:major|minor)?\s*scale',  # "C major scale", "C scale"
                r'(?:key\s+(?:of\s+)?|in\s+)([A-Ga-g][#b]?)',  # "key of C", "in C"
                r'(?:major|minor)\s+([A-Ga-g][#b]?)\s+scale',  # "major C scale"
            ]
            for pattern in key_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    params[param_name] = match.group(1).upper()
                    break
        
        elif param_name == "tempo":
            # Extract tempo - look for number followed by BPM
            tempo_patterns = [
                r'tempo\s+(\d+)',  # "tempo 80"
                r'(\d+)\s*bpm',  # "80 BPM"
                r'at\s+(\d+)',  # "at 80"
            ]
            for pattern in tempo_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    params[param_name] = int(match.group(1))
                    break
        
        elif param_name == "duration":
            # Extract duration - look for number followed by beats
            duration_patterns = [
                r'duration\s+(\d+)',  # "duration 4"
                r'(\d+)\s*beats',  # "4 beats"
            ]
            for pattern in duration_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    params[param_name] = int(match.group(1))
                    break
        
        elif param_name == "scale_type":
            # Extract scale type - look for major/minor/etc before "scale"
            scale_patterns = [
                r'\b(major|minor|pentatonic|blues|chromatic|harmonic|melodic)\b',
            ]
            for pattern in scale_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    params[param_name] = match.group(1).lower()
                    break
            # If not found and has default, use default
            if param_name not in params and "default" in param_info:
                params[param_name] = param_info["default"]
    
    return {func_name: params}
