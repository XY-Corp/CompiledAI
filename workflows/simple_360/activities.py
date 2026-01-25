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
    
    Uses regex and string matching to extract values - no LLM calls needed.
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
    
    if not funcs:
        return {"error": "No functions provided"}
    
    func = funcs[0]
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    required_params = func.get("parameters", {}).get("required", [])
    
    # Extract parameters based on schema
    params = {}
    query_lower = query.lower()
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_type == "integer" or param_type == "number":
            # Extract numbers from query
            # Look for patterns like "less than X", "under X", "max X", "X calories"
            calorie_patterns = [
                r'less than\s+(\d+)',
                r'under\s+(\d+)',
                r'max(?:imum)?\s+(\d+)',
                r'(\d+)\s*calories',
                r'only\s+(\d+)',
                r'below\s+(\d+)',
            ]
            
            for pattern in calorie_patterns:
                match = re.search(pattern, query_lower)
                if match:
                    params[param_name] = int(match.group(1))
                    break
        
        elif param_type == "string":
            # For recipe name, extract the dish name
            if "recipe" in param_desc or "name" in param_desc:
                # Patterns to extract recipe/dish name
                recipe_patterns = [
                    r'recipe for\s+([a-zA-Z\s]+?)(?:\s+which|\s+that|\s+with|\s+containing|$)',
                    r'find\s+(?:a\s+)?([a-zA-Z\s]+?)\s+recipe',
                    r'make\s+([a-zA-Z\s]+?)(?:\s+which|\s+that|\s+with|$)',
                    r'cook\s+([a-zA-Z\s]+?)(?:\s+which|\s+that|\s+with|$)',
                ]
                
                for pattern in recipe_patterns:
                    match = re.search(pattern, query_lower)
                    if match:
                        recipe_name = match.group(1).strip()
                        # Clean up the recipe name
                        recipe_name = re.sub(r'\s+', ' ', recipe_name)
                        params[param_name] = recipe_name
                        break
    
    # Ensure required params are present
    for req_param in required_params:
        if req_param not in params:
            # Try a more aggressive extraction for missing required params
            if params_schema.get(req_param, {}).get("type") == "string":
                # For string params, try to extract key phrases
                words = re.findall(r'\b[a-zA-Z]+\b', query)
                # Filter out common words
                stop_words = {'find', 'a', 'the', 'for', 'which', 'contains', 'only', 'less', 'than', 'recipe', 'with', 'that', 'is', 'are', 'and', 'or'}
                meaningful_words = [w for w in words if w.lower() not in stop_words]
                if meaningful_words:
                    params[req_param] = ' '.join(meaningful_words[:3])
    
    return {func_name: params}
