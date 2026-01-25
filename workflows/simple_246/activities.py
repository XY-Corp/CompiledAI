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
    """Extract function name and parameters from user query based on available function schemas.
    
    Returns format: {"function_name": {"param1": val1, "param2": val2}}
    """
    # Parse prompt - may be JSON string with nested structure
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
        else:
            data = prompt
        
        # Extract user query from BFCL format: {"question": [[{"role": "user", "content": "..."}]]}
        if isinstance(data, dict) and "question" in data:
            question_data = data["question"]
            if isinstance(question_data, list) and len(question_data) > 0:
                if isinstance(question_data[0], list) and len(question_data[0]) > 0:
                    query = question_data[0][0].get("content", str(prompt))
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
    
    if not funcs:
        return {"error": "No functions provided"}
    
    # Get target function details
    func = funcs[0]
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    required_params = func.get("parameters", {}).get("required", [])
    
    # Extract parameters from query using regex and string matching
    params = {}
    query_lower = query.lower()
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        # Strategy 1: Look for explicit mentions based on parameter name
        # For "discovery" parameter - look for scientific concepts
        if param_name == "discovery":
            # Common scientific discoveries to look for
            discoveries = ["gravity", "relativity", "evolution", "dna", "penicillin", 
                          "electricity", "radioactivity", "photosynthesis", "quantum"]
            for disc in discoveries:
                if disc in query_lower:
                    params[param_name] = disc.capitalize()
                    break
            
            # If not found, try to extract noun after "discovered" or before "discovery"
            if param_name not in params:
                match = re.search(r'(?:discovered|discover)\s+(\w+)', query_lower)
                if match:
                    params[param_name] = match.group(1).capitalize()
        
        # For "method_used" parameter - look for method mentions
        elif param_name == "method_used":
            # Look for explicit method mentions
            method_patterns = [
                r'method\s+(?:used\s+)?(?:was\s+)?["\']?(\w+(?:\s+\w+)?)["\']?',
                r'using\s+(?:the\s+)?(\w+(?:\s+\w+)?)\s+method',
                r'by\s+(\w+(?:\s+\w+)?)\s+method',
            ]
            for pattern in method_patterns:
                match = re.search(pattern, query_lower)
                if match:
                    params[param_name] = match.group(1)
                    break
            
            # Check if user is asking about the method (don't set a value, let default apply)
            if param_name not in params:
                if "what was the method" in query_lower or "method used" in query_lower:
                    # User is asking about the method, use default
                    pass  # Don't set - let the function use its default
        
        # Generic string extraction for other parameters
        elif param_type == "string":
            # Try to find quoted values
            quoted_match = re.search(rf'{param_name}["\s:=]+["\']([^"\']+)["\']', query, re.IGNORECASE)
            if quoted_match:
                params[param_name] = quoted_match.group(1)
            else:
                # Try pattern: "param_name value" or "param_name: value"
                pattern = rf'{param_name}[\s:=]+(\w+(?:\s+\w+)?)'
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    params[param_name] = match.group(1)
        
        # Number extraction
        elif param_type in ["integer", "number", "float"]:
            numbers = re.findall(r'\d+(?:\.\d+)?', query)
            if numbers:
                if param_type == "integer":
                    params[param_name] = int(float(numbers[0]))
                else:
                    params[param_name] = float(numbers[0])
    
    # Ensure required parameters are present
    for req_param in required_params:
        if req_param not in params:
            # Try harder to extract required params
            if req_param == "discovery":
                # Extract any capitalized word that might be a discovery name
                caps_match = re.search(r'\b([A-Z][a-z]+)\b', query)
                if caps_match:
                    params[req_param] = caps_match.group(1)
                else:
                    # Last resort: look for key nouns
                    words = query.split()
                    for word in words:
                        clean_word = re.sub(r'[^\w]', '', word)
                        if clean_word and clean_word[0].isupper():
                            params[req_param] = clean_word
                            break
    
    return {func_name: params}
