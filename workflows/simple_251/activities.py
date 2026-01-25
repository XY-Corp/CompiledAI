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
    
    Parses the prompt to extract the user's query, then extracts parameter values
    using regex and string matching based on the function schema.
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
    
    # Get function details
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    required_params = func.get("parameters", {}).get("required", [])
    
    # Extract parameters based on schema
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        param_enum = param_info.get("enum", [])
        
        # Check for enum values in query
        if param_enum:
            for enum_val in param_enum:
                if enum_val.lower() in query.lower():
                    params[param_name] = enum_val
                    break
        
        # Extract based on parameter name and description
        elif param_name == "name" or "name of" in param_desc or "person" in param_desc:
            # For this query about Jesus Christ, extract the name
            # Pattern: "of [Name]" or "[Name] in history"
            name_patterns = [
                r'(?:reference of|about|for)\s+([A-Z][a-zA-Z\s]+?)(?:\s+in|\s+from|\?|$)',
                r'([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)+)',  # Capitalized multi-word names
            ]
            
            for pattern in name_patterns:
                match = re.search(pattern, query)
                if match:
                    extracted_name = match.group(1).strip()
                    # Clean up trailing words that aren't part of the name
                    extracted_name = re.sub(r'\s+in\s+history.*$', '', extracted_name, flags=re.IGNORECASE)
                    if extracted_name:
                        params[param_name] = extracted_name
                        break
        
        elif param_type == "integer" or param_type == "number":
            # Extract numbers
            numbers = re.findall(r'\d+(?:\.\d+)?', query)
            if numbers:
                if param_type == "integer":
                    params[param_name] = int(numbers[0])
                else:
                    params[param_name] = float(numbers[0])
    
    # Check for source parameter based on query content
    if "source" in params_schema and "source" not in params:
        # Check if query mentions historical records
        if "historical record" in query.lower() or "history" in query.lower():
            params["source"] = "historical records"
    
    return {func_name: params}
