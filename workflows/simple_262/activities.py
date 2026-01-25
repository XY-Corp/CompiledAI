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
    
    # Parse prompt (may be JSON string with nested structure)
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
    
    # Parse functions (may be JSON string)
    try:
        if isinstance(functions, str):
            funcs = json.loads(functions)
        else:
            funcs = functions
    except (json.JSONDecodeError, TypeError):
        funcs = []
    
    # Get function schema
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters using regex and string matching
    params = {}
    query_lower = query.lower()
    
    for param_name, param_info in params_schema.items():
        param_desc = param_info.get("description", "").lower()
        
        if param_name == "size":
            # Extract size pattern like "12x18", "12 x 18", "12 by 18"
            size_match = re.search(r'(\d+)\s*[xX×]\s*(\d+)', query)
            if size_match:
                params["size"] = f"{size_match.group(1)}x{size_match.group(2)}"
            else:
                # Try "width by height" pattern
                size_match = re.search(r'(\d+)\s*by\s*(\d+)', query_lower)
                if size_match:
                    params["size"] = f"{size_match.group(1)}x{size_match.group(2)}"
        
        elif param_name == "medium":
            # Extract medium type (oil, acrylic, watercolor, etc.)
            medium_patterns = [
                r'medium\s+to\s+(\w+)',
                r'(\w+)\s+medium',
                r'to\s+(oil|acrylic|watercolor|pastel|charcoal|pencil|ink|gouache)',
            ]
            for pattern in medium_patterns:
                medium_match = re.search(pattern, query_lower)
                if medium_match:
                    params["medium"] = medium_match.group(1)
                    break
        
        elif param_name == "dominant_color" or "color" in param_name:
            # Extract color
            color_patterns = [
                r'(\w+)\s+dominant\s+color',
                r'dominant\s+color\s+(?:to\s+)?(\w+)',
                r'(\w+)\s+color',
                r'color\s+(?:to\s+)?(\w+)',
            ]
            for pattern in color_patterns:
                color_match = re.search(pattern, query_lower)
                if color_match:
                    color = color_match.group(1)
                    # Filter out common non-color words
                    if color not in ["the", "a", "an", "with", "and", "to", "my", "painting"]:
                        params["dominant_color"] = color
                        break
    
    return {func_name: params}
