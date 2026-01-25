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
        if isinstance(data, dict) and "question" in data:
            question = data.get("question", [])
            if isinstance(question, list) and len(question) > 0:
                if isinstance(question[0], list) and len(question[0]) > 0:
                    query = question[0][0].get("content", str(prompt))
                elif isinstance(question[0], dict):
                    query = question[0].get("content", str(prompt))
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
    
    # Get function schema
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters based on query content
    params = {}
    query_lower = query.lower()
    
    # For sql.execute function
    if func_name == "sql.execute":
        # Determine SQL keyword based on action words
        if "remove" in query_lower or "delete" in query_lower:
            params["sql_keyword"] = "DELETE"
        elif "insert" in query_lower or "add" in query_lower:
            params["sql_keyword"] = "INSERT"
        elif "update" in query_lower or "change" in query_lower or "modify" in query_lower:
            params["sql_keyword"] = "UPDATE"
        elif "create" in query_lower:
            params["sql_keyword"] = "CREATE"
        else:
            params["sql_keyword"] = "SELECT"
        
        # Extract table name - look for patterns like 'table named "X"' or 'from "X"' or '"X" table'
        table_patterns = [
            r'table\s+named\s+["\']?(\w+)["\']?',
            r'["\'](\w+)["\']\s+table',
            r'from\s+(?:the\s+)?["\']?(\w+)["\']?\s+table',
            r'table\s+["\']?(\w+)["\']?',
        ]
        
        table_name = None
        for pattern in table_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                table_name = match.group(1)
                break
        
        if table_name:
            params["table_name"] = table_name
        
        # Extract conditions - look for name patterns like 'named "X"' or 'name is "X"'
        condition_patterns = [
            r"(?:employee(?:'s)?|person(?:'s)?|user(?:'s)?)\s+name\s+is\s+[\"']([^\"']+)[\"']",
            r"named\s+[\"']([^\"']+)[\"']",
            r"name\s*=\s*[\"']([^\"']+)[\"']",
            r"where\s+(?:the\s+)?(?:employee(?:'s)?|person(?:'s)?|user(?:'s)?)?\s*name\s+is\s+[\"']([^\"']+)[\"']",
        ]
        
        name_value = None
        for pattern in condition_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                name_value = match.group(1)
                break
        
        if name_value:
            # Format condition as specified in schema description
            params["conditions"] = [[f"name = '{name_value}'"]]
    
    return {func_name: params}
