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
    """Extract function name and parameters from user query. Returns {func_name: {params}}."""
    
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
    
    # Extract parameters based on the query
    params = {}
    query_lower = query.lower()
    
    # For map_service.get_directions - extract start, end, and avoid
    if "directions" in func_name.lower() or "route" in func_name.lower():
        # Extract start and end locations
        # Pattern: "from X to Y"
        from_to_match = re.search(r'from\s+([A-Za-z\s]+?)\s+to\s+([A-Za-z\s]+?)(?:\s+avoiding|\s+avoid|\s*$|\.)', query, re.IGNORECASE)
        
        if from_to_match:
            params["start"] = from_to_match.group(1).strip()
            params["end"] = from_to_match.group(2).strip()
        else:
            # Fallback: try to find location names
            locations = re.findall(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)', query)
            if len(locations) >= 2:
                params["start"] = locations[0]
                params["end"] = locations[1]
        
        # Extract avoid preferences
        avoid_list = []
        
        # Check for "avoiding" or "avoid" followed by items
        avoid_match = re.search(r'avoid(?:ing)?\s+(.+?)(?:\.|$)', query, re.IGNORECASE)
        if avoid_match:
            avoid_text = avoid_match.group(1).lower()
            
            # Check for each possible avoid option
            if "highway" in avoid_text:
                avoid_list.append("highways")
            if "toll" in avoid_text:
                avoid_list.append("tolls")
            if "ferr" in avoid_text:
                avoid_list.append("ferries")
        
        # Also check the whole query for these keywords
        if not avoid_list:
            if "highway" in query_lower:
                avoid_list.append("highways")
            if "toll" in query_lower:
                avoid_list.append("tolls")
            if "ferr" in query_lower:
                avoid_list.append("ferries")
        
        if avoid_list:
            params["avoid"] = avoid_list
    
    else:
        # Generic extraction for other functions
        for param_name, param_info in params_schema.items():
            param_type = param_info.get("type", "string") if isinstance(param_info, dict) else "string"
            
            if param_type in ["integer", "number", "float"]:
                # Extract numbers
                numbers = re.findall(r'\d+(?:\.\d+)?', query)
                if numbers:
                    if param_type == "integer":
                        params[param_name] = int(numbers[0])
                    else:
                        params[param_name] = float(numbers[0])
            elif param_type == "array":
                # Try to extract list items
                items = re.findall(r'[\w\s]+', query)
                if items:
                    params[param_name] = [item.strip() for item in items if item.strip()]
            else:
                # String type - try to extract relevant text
                match = re.search(rf'{param_name}[:\s]+([^\.,]+)', query, re.IGNORECASE)
                if match:
                    params[param_name] = match.group(1).strip()
    
    return {func_name: params}
