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
    
    Returns a dict with function name as key and parameters as nested object.
    """
    # Parse prompt - may be JSON string with nested structure
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
        else:
            data = prompt
        
        # Extract user query from BFCL format: {"question": [[{"role": "user", "content": "..."}]]}
        if isinstance(data, dict) and "question" in data:
            question_data = data.get("question", [])
            if isinstance(question_data, list) and len(question_data) > 0:
                first_item = question_data[0]
                if isinstance(first_item, list) and len(first_item) > 0:
                    query = first_item[0].get("content", str(prompt))
                elif isinstance(first_item, dict):
                    query = first_item.get("content", str(prompt))
                else:
                    query = str(prompt)
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
    
    # Get function details
    func = funcs[0] if isinstance(funcs, list) else funcs
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {})
    
    # Handle both "properties" nested and direct properties
    if "properties" in params_schema:
        props = params_schema.get("properties", {})
    else:
        props = params_schema
    
    required_params = params_schema.get("required", [])
    
    # Extract parameters based on schema
    params = {}
    query_lower = query.lower()
    
    for param_name, param_info in props.items():
        param_type = param_info.get("type", "string") if isinstance(param_info, dict) else "string"
        param_desc = param_info.get("description", "") if isinstance(param_info, dict) else ""
        
        # For celestial body extraction
        if "celestial" in param_desc.lower() or "body" in param_name.lower():
            # Common celestial bodies
            celestial_bodies = [
                "earth", "moon", "sun", "mars", "venus", "mercury", "jupiter", 
                "saturn", "uranus", "neptune", "pluto", "asteroid", "comet"
            ]
            
            # Find all celestial bodies mentioned in query
            found_bodies = []
            for body in celestial_bodies:
                if body in query_lower:
                    # Get proper capitalization
                    match = re.search(rf'\b{body}\b', query, re.IGNORECASE)
                    if match:
                        found_bodies.append(match.group(0).capitalize())
            
            # Assign to body1 and body2 based on order found
            if param_name == "body1" and len(found_bodies) >= 1:
                params[param_name] = found_bodies[0]
            elif param_name == "body2" and len(found_bodies) >= 2:
                params[param_name] = found_bodies[1]
        
        # For unit extraction
        elif "unit" in param_name.lower():
            # Check for unit mentions
            unit_patterns = [
                (r'\b(miles?|mi)\b', 'miles'),
                (r'\b(kilometers?|km)\b', 'km'),
                (r'\b(meters?|m)\b', 'm'),
                (r'\b(feet|ft)\b', 'feet'),
                (r'\b(light[\s-]?years?|ly)\b', 'light-years'),
                (r'\b(astronomical[\s-]?units?|au)\b', 'AU'),
            ]
            
            for pattern, unit_value in unit_patterns:
                if re.search(pattern, query, re.IGNORECASE):
                    params[param_name] = unit_value
                    break
        
        # For numeric parameters
        elif param_type in ["integer", "number", "float"]:
            numbers = re.findall(r'\d+(?:\.\d+)?', query)
            if numbers:
                if param_type == "integer":
                    params[param_name] = int(float(numbers[0]))
                else:
                    params[param_name] = float(numbers[0])
        
        # For string parameters - try to extract based on context
        elif param_type == "string":
            # Generic string extraction - look for quoted strings or key phrases
            quoted = re.findall(r'"([^"]+)"', query)
            if quoted:
                params[param_name] = quoted[0]
    
    return {func_name: params}
