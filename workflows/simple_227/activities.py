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
    
    # Parse prompt (may be JSON string with nested structure)
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
        else:
            data = prompt
        
        # Extract user query from BFCL format: {"question": [[{"role": "user", "content": "..."}]]}
        if isinstance(data, dict) and "question" in data:
            question = data["question"]
            if isinstance(question, list) and len(question) > 0:
                if isinstance(question[0], list) and len(question[0]) > 0:
                    query = question[0][0].get("content", str(prompt))
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
    
    # Extract parameters based on schema
    params = {}
    query_lower = query.lower()
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_type == "string":
            # For personality type - look for common patterns
            if "personality" in param_desc or "type" in param_name:
                # Match personality types like ENFJ, INTJ, INFP, etc.
                type_match = re.search(r'\b([EI][NS][TF][JP])\b', query, re.IGNORECASE)
                if type_match:
                    params[param_name] = type_match.group(1).upper()
        
        elif param_type == "array":
            # For traits array - look for strengths/weaknesses mentions
            if "traits" in param_name or "trait" in param_desc:
                items_info = param_info.get("items", {})
                enum_values = items_info.get("enum", [])
                
                traits = []
                for enum_val in enum_values:
                    # Check if the trait is mentioned in the query
                    if enum_val.lower() in query_lower:
                        traits.append(enum_val)
                
                # Also check for singular forms
                if "strength" in query_lower and "strengths" in enum_values and "strengths" not in traits:
                    traits.append("strengths")
                if "weakness" in query_lower and "weaknesses" in enum_values and "weaknesses" not in traits:
                    traits.append("weaknesses")
                
                if traits:
                    params[param_name] = traits
        
        elif param_type in ["integer", "number", "float"]:
            # Extract numbers
            numbers = re.findall(r'\d+(?:\.\d+)?', query)
            if numbers:
                if param_type == "integer":
                    params[param_name] = int(numbers[0])
                else:
                    params[param_name] = float(numbers[0])
    
    return {func_name: params}
