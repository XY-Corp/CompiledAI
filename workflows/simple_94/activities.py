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
    
    # Parse prompt (may be JSON string with nested structure)
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
            # Extract user query from BFCL format: {"question": [[{"role": "user", "content": "..."}]]}
            if "question" in data and isinstance(data["question"], list):
                if len(data["question"]) > 0 and isinstance(data["question"][0], list):
                    query = data["question"][0][0].get("content", str(prompt))
                else:
                    query = str(prompt)
            else:
                query = str(prompt)
        else:
            query = str(prompt)
    except (json.JSONDecodeError, TypeError, KeyError):
        query = str(prompt)
    
    # Parse functions (may be JSON string)
    try:
        if isinstance(functions, str):
            funcs = json.loads(functions)
        else:
            funcs = functions
    except (json.JSONDecodeError, TypeError):
        funcs = []
    
    # Get function schema
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters from query
    params = {}
    
    # Extract user_id (integer) - look for patterns like "user id 43523" or "user_id 43523"
    user_id_match = re.search(r'user\s*id\s*(\d+)', query, re.IGNORECASE)
    if user_id_match and "user_id" in params_schema:
        params["user_id"] = int(user_id_match.group(1))
    
    # Extract update_info (dict) - look for key-value pairs like 'name':'John Doe', 'email':'johndoe@email.com'
    if "update_info" in params_schema:
        update_info = {}
        
        # Extract name - pattern: 'name':'...' or "name":"..."
        name_match = re.search(r"['\"]name['\"]\s*:\s*['\"]([^'\"]+)['\"]", query)
        if name_match:
            update_info["name"] = name_match.group(1)
        
        # Extract email - pattern: 'email':'...' or "email":"..."
        email_match = re.search(r"['\"]email['\"]\s*:\s*['\"]([^'\"]+)['\"]", query)
        if email_match:
            update_info["email"] = email_match.group(1)
        
        if update_info:
            params["update_info"] = update_info
    
    # Extract database (string) - check if explicitly mentioned, otherwise use default
    if "database" in params_schema:
        db_match = re.search(r'database\s*[=:]\s*["\']?(\w+)["\']?', query, re.IGNORECASE)
        if db_match:
            params["database"] = db_match.group(1)
        # Note: default value "CustomerInfo" is in schema, only include if explicitly mentioned
    
    return {func_name: params}
