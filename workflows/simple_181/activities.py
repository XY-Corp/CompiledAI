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
    if isinstance(functions, str):
        try:
            functions = json.loads(functions)
        except json.JSONDecodeError:
            functions = []
    
    if not functions:
        return {"error": "No functions provided"}
    
    func = functions[0]
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters based on schema
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        
        if param_name == "case_number":
            # Extract case number - pattern like '123456-ABC' or similar alphanumeric with dashes
            case_match = re.search(r"case\s+number\s+['\"]?([A-Za-z0-9\-]+)['\"]?", query, re.IGNORECASE)
            if not case_match:
                # Try pattern with quotes
                case_match = re.search(r"['\"]([A-Za-z0-9\-]+)['\"]", query)
            if case_match:
                params[param_name] = case_match.group(1)
        
        elif param_name == "court_location":
            # Extract court location - look for "in X court" or "filed in X"
            location_match = re.search(r"(?:in|at)\s+([A-Za-z\s]+?)\s+court", query, re.IGNORECASE)
            if not location_match:
                # Try "filed in X"
                location_match = re.search(r"filed\s+in\s+([A-Za-z\s]+?)(?:\s+court|\s+with|\s*$)", query, re.IGNORECASE)
            if location_match:
                params[param_name] = location_match.group(1).strip()
        
        elif param_name == "with_verdict":
            # Check for verdict-related keywords
            if param_type == "boolean":
                # Look for "with verdict" or similar phrases
                has_verdict = bool(re.search(r"\bwith\s+verdict\b|\binclude\s+verdict\b|\bverdict\s+details\b", query, re.IGNORECASE))
                params[param_name] = has_verdict
    
    return {func_name: params}
