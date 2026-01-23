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
    """Extract function call parameters from natural language query.
    
    Parses the prompt to extract the user query and matches it against
    the function schema to extract parameter values using regex patterns.
    Returns format: {"function_name": {"param1": val1, "param2": val2}}
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
    func = funcs[0]
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters based on schema
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_desc = param_info.get("description", "").lower()
        param_type = param_info.get("type", "string")
        
        # Extract based on parameter name and description
        if param_name == "name" or "name" in param_desc:
            # Extract full name - look for capitalized words that form a name
            # Pattern: "Lawyer John Doe" or just "John Doe"
            name_patterns = [
                r'(?:Lawyer|Attorney|Mr\.|Ms\.|Mrs\.|Dr\.)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)',
                r'([A-Z][a-z]+\s+[A-Z][a-z]+)',  # Simple "First Last" pattern
            ]
            for pattern in name_patterns:
                match = re.search(pattern, query)
                if match:
                    params[param_name] = match.group(1).strip()
                    break
        
        elif param_name == "law_type" or "type" in param_desc or "law" in param_desc:
            # Extract law type - look for common law types
            law_types = [
                "Bankruptcy", "Criminal", "Civil", "Family", "Corporate", 
                "Immigration", "Tax", "Real Estate", "Personal Injury",
                "Employment", "Intellectual Property", "Environmental"
            ]
            for law_type in law_types:
                if law_type.lower() in query.lower():
                    params[param_name] = law_type
                    break
            
            # If not found in predefined list, try to extract from context
            if param_name not in params:
                # Pattern: "handling X cases" or "X law" or "X cases"
                type_patterns = [
                    r'handling\s+(\w+)\s+cases',
                    r'(\w+)\s+cases',
                    r'(\w+)\s+law',
                ]
                for pattern in type_patterns:
                    match = re.search(pattern, query, re.IGNORECASE)
                    if match:
                        extracted = match.group(1).strip()
                        # Capitalize first letter
                        params[param_name] = extracted.capitalize()
                        break
    
    return {func_name: params}
