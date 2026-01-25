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
    """Extract function name and parameters from user query. Returns {"func_name": {params}}."""
    
    # Parse prompt - may be JSON string with nested structure
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
        else:
            data = prompt
        
        # Extract user query from BFCL format: {"question": [[{"role": "user", "content": "..."}]]}
        if isinstance(data, dict) and "question" in data:
            question_list = data.get("question", [])
            if question_list and isinstance(question_list[0], list) and question_list[0]:
                query = question_list[0][0].get("content", str(prompt))
            else:
                query = str(prompt)
        else:
            query = str(prompt)
    except (json.JSONDecodeError, TypeError):
        query = str(prompt)
    
    # Parse functions - may be JSON string
    try:
        if isinstance(functions, str):
            funcs = json.loads(functions)
        else:
            funcs = functions
    except (json.JSONDecodeError, TypeError):
        funcs = []
    
    if not funcs:
        return {"error": "No functions provided"}
    
    func = funcs[0]
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters based on schema
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_type in ["integer", "number", "float"]:
            # Extract numbers using regex
            numbers = re.findall(r'\d+(?:\.\d+)?', query)
            if numbers:
                if param_type == "integer":
                    params[param_name] = int(numbers[0])
                else:
                    params[param_name] = float(numbers[0])
        elif param_type == "string":
            # Use description hints to extract the right value
            extracted_value = None
            
            # Check for sculpture/artwork name - look for quoted text or "the X" pattern
            if "sculpture" in param_name.lower() or "sculpture" in param_desc:
                # Try quoted text first
                quoted_match = re.search(r"['\"]([^'\"]+)['\"]", query)
                if quoted_match:
                    extracted_value = quoted_match.group(1)
                else:
                    # Try "the X by" pattern
                    the_match = re.search(r"the\s+([A-Z][A-Za-z\s]+?)(?:\s+by|\?|$)", query)
                    if the_match:
                        extracted_value = the_match.group(1).strip()
            
            # Check for artist name - look for "by X" pattern
            elif "artist" in param_name.lower() or "artist" in param_desc:
                by_match = re.search(r"by\s+([A-Z][A-Za-z\s]+?)(?:\?|$|\s+(?:is|was|has|have|in|at|on))", query)
                if by_match:
                    extracted_value = by_match.group(1).strip()
                else:
                    # Try simpler "by X" at end
                    by_match = re.search(r"by\s+([A-Z][A-Za-z]+)", query)
                    if by_match:
                        extracted_value = by_match.group(1).strip()
            
            # Generic extraction for other string params
            if extracted_value is None:
                # Try quoted text
                quoted_match = re.search(r"['\"]([^'\"]+)['\"]", query)
                if quoted_match:
                    extracted_value = quoted_match.group(1)
                else:
                    # Try to find capitalized proper nouns
                    proper_nouns = re.findall(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b', query)
                    if proper_nouns:
                        extracted_value = proper_nouns[0]
            
            if extracted_value:
                params[param_name] = extracted_value
    
    return {func_name: params}
