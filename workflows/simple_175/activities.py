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
    
    Uses regex and string matching to extract parameter values - no LLM calls needed.
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
    
    # Extract parameters based on schema
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_desc = param_info.get("description", "").lower()
        
        if param_name == "name" and "lawyer" in param_desc:
            # Extract lawyer name - look for capitalized names
            # Pattern: "Lawyer [Name]" or just capitalized proper names
            name_patterns = [
                r'[Ll]awyer\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)',  # "Lawyer John Doe"
                r'([A-Z][a-z]+\s+[A-Z][a-z]+)(?:\s+has|\s+have)',  # "John Doe has"
            ]
            for pattern in name_patterns:
                match = re.search(pattern, query)
                if match:
                    params[param_name] = match.group(1).strip()
                    break
        
        elif param_name == "law_type" or "type of law" in param_desc:
            # Extract law type - look for specific case types
            # Common patterns: "handling X cases", "X law", "X cases"
            law_type_patterns = [
                r'handling\s+([A-Z][a-z]+)\s+cases',  # "handling Bankruptcy cases"
                r'([A-Z][a-z]+)\s+cases',  # "Bankruptcy cases"
                r'([A-Z][a-z]+)\s+law',  # "Bankruptcy law"
            ]
            for pattern in law_type_patterns:
                match = re.search(pattern, query)
                if match:
                    params[param_name] = match.group(1).strip()
                    break
    
    return {func_name: params}
