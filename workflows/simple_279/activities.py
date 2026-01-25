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
    """Extract function name and parameters from user query and function schema.
    
    Returns a dict with function name as key and extracted parameters as value.
    """
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
        
        if param_name == "brand":
            # Extract brand - look for known instrument brands
            brand_patterns = [
                r'\b(Fender|Gibson|Martin|Taylor|Yamaha|Ibanez|PRS|Epiphone|Squier|Gretsch)\b',
            ]
            for pattern in brand_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    params["brand"] = match.group(1)
                    break
        
        elif param_name == "model":
            # Extract model - look for text between brand and finish/price keywords
            # Pattern: brand followed by model name
            model_patterns = [
                # "Fender American Professional II Stratocaster" pattern
                r'(?:Fender|Gibson|Martin|Taylor|Yamaha|Ibanez|PRS|Epiphone|Squier|Gretsch)\s+([A-Za-z0-9\s]+?)(?:\s+in\s+|\s+with\s+|\?|$)',
            ]
            for pattern in model_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    model = match.group(1).strip()
                    # Clean up - remove trailing "in" or finish words
                    model = re.sub(r'\s+(in|with|finish|color).*$', '', model, flags=re.IGNORECASE).strip()
                    if model:
                        params["model"] = model
                        break
        
        elif param_name == "finish":
            # Extract finish - look for "in X Finish" or "X Finish" patterns
            finish_patterns = [
                r'in\s+([A-Za-z\s]+?)\s*[Ff]inish',
                r'([A-Za-z]+)\s+[Ff]inish',
                r'in\s+([A-Za-z]+)\s*\?',
            ]
            for pattern in finish_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    params["finish"] = match.group(1).strip()
                    break
    
    return {func_name: params}
