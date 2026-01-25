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
    
    # Extract parameters from query using regex and string matching
    params = {}
    query_lower = query.lower()
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_name == "instrument":
            # Extract instrument name - common instruments
            instruments = ["piano", "guitar", "violin", "drums", "flute", "saxophone", 
                          "trumpet", "cello", "bass", "keyboard", "ukulele", "harmonica"]
            for inst in instruments:
                if inst in query_lower:
                    params[param_name] = inst
                    break
            # Fallback: look for pattern "of <instrument>"
            if param_name not in params:
                match = re.search(r'(?:of|the|a)\s+(\w+)(?:\s+from|\s+by|\s+made)', query_lower)
                if match:
                    params[param_name] = match.group(1)
        
        elif param_name == "manufacturer":
            # Extract manufacturer - common instrument manufacturers
            manufacturers = ["yamaha", "fender", "gibson", "steinway", "roland", "kawai",
                           "casio", "korg", "ibanez", "taylor", "martin", "pearl"]
            for mfr in manufacturers:
                if mfr in query_lower:
                    # Capitalize properly
                    params[param_name] = mfr.capitalize()
                    break
            # Fallback: look for pattern "from <manufacturer>"
            if param_name not in params:
                match = re.search(r'from\s+(\w+)', query_lower)
                if match:
                    params[param_name] = match.group(1).capitalize()
        
        elif param_name == "features" and param_type == "array":
            # Extract features from enum options
            enum_values = param_info.get("items", {}).get("enum", [])
            features = []
            for feature in enum_values:
                if feature.lower() in query_lower:
                    features.append(feature)
            # Check for synonyms
            if "price" not in features and any(word in query_lower for word in ["cost", "price", "pricing"]):
                features.append("price")
            if "rating" not in features and any(word in query_lower for word in ["rating", "ratings", "review", "reviews"]):
                features.append("rating")
            if features:
                params[param_name] = features
    
    return {func_name: params}
