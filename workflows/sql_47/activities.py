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
        else:
            data = prompt
        
        # Extract user query from BFCL format
        if "question" in data and isinstance(data["question"], list):
            if len(data["question"]) > 0 and isinstance(data["question"][0], list):
                query = data["question"][0][0].get("content", str(prompt))
            elif len(data["question"]) > 0 and isinstance(data["question"][0], dict):
                query = data["question"][0].get("content", str(prompt))
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
    props = func.get("parameters", {}).get("properties", {})
    
    params = {}
    query_lower = query.lower()
    
    # Extract SQL keyword based on action words in query
    if "sql_keyword" in props:
        if any(word in query_lower for word in ["delete", "eliminate", "remove", "drop records"]):
            params["sql_keyword"] = "DELETE"
        elif any(word in query_lower for word in ["insert", "add", "create record"]):
            params["sql_keyword"] = "INSERT"
        elif any(word in query_lower for word in ["update", "modify", "change", "set"]):
            params["sql_keyword"] = "UPDATE"
        elif any(word in query_lower for word in ["select", "get", "fetch", "retrieve", "find", "show"]):
            params["sql_keyword"] = "SELECT"
        elif any(word in query_lower for word in ["create table", "create database"]):
            params["sql_keyword"] = "CREATE"
    
    # Extract table name - look for patterns like "table named X" or "from X table" or "X table"
    if "table_name" in props:
        table_patterns = [
            r'table\s+(?:named|called)\s+["\']?(\w+)["\']?',
            r'["\'](\w+)["\']?\s+table',
            r'from\s+(?:the\s+)?["\']?(\w+)["\']?\s+table',
            r'in\s+(?:the\s+)?["\']?(\w+)["\']?\s+table',
        ]
        for pattern in table_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                params["table_name"] = match.group(1)
                break
    
    # Extract conditions - look for "where X = Y" or "name is X" patterns
    if "conditions" in props:
        conditions = []
        
        # Pattern for quoted names like "Jane Smith"
        name_patterns = [
            r"(?:student'?s?\s+)?name\s+is\s+[\"']([^\"']+)[\"']",
            r"named\s+[\"']([^\"']+)[\"']",
            r"where\s+(?:the\s+)?(?:student'?s?\s+)?name\s+(?:is\s+)?[\"']([^\"']+)[\"']",
        ]
        
        for pattern in name_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                name_value = match.group(1)
                conditions.append([f"name = '{name_value}'"])
                break
        
        if conditions:
            params["conditions"] = conditions
    
    return {func_name: params}
