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
    """Extract function call parameters from natural language query about SQL operations."""
    
    # Parse prompt (may be JSON string with nested structure)
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
        else:
            data = prompt
        
        # Extract user query from BFCL format
        if "question" in data and isinstance(data["question"], list):
            query = data["question"][0][0].get("content", str(prompt))
        else:
            query = str(prompt)
    except (json.JSONDecodeError, KeyError, IndexError, TypeError):
        query = str(prompt)
    
    # Parse functions (may be JSON string)
    try:
        if isinstance(functions, str):
            funcs = json.loads(functions)
        else:
            funcs = functions
    except json.JSONDecodeError:
        funcs = []
    
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "sql.execute")
    
    query_lower = query.lower()
    params = {}
    
    # Determine SQL keyword based on query content
    if "change" in query_lower or "update" in query_lower or "set" in query_lower or "modify" in query_lower:
        params["sql_keyword"] = "UPDATE"
    elif "insert" in query_lower or "add" in query_lower:
        params["sql_keyword"] = "INSERT"
    elif "delete" in query_lower or "remove" in query_lower:
        params["sql_keyword"] = "DELETE"
    elif "create" in query_lower:
        params["sql_keyword"] = "CREATE"
    else:
        params["sql_keyword"] = "SELECT"
    
    # Extract table name - look for patterns like 'table named "X"' or 'table "X"'
    table_match = re.search(r'table\s+(?:named\s+)?["\']?(\w+)["\']?', query, re.IGNORECASE)
    if table_match:
        params["table_name"] = table_match.group(1)
    
    # Extract column names mentioned in the query
    # Look for quoted column names or common patterns
    column_matches = re.findall(r'["\'](\w+(?:ID|Grade|Name|Date|Value)?)["\']', query)
    
    # For UPDATE operations, extract the column being updated and its new value
    if params["sql_keyword"] == "UPDATE":
        # Pattern: change/update the "ColumnName" ... to VALUE
        update_match = re.search(r'(?:change|update|set)\s+(?:the\s+)?["\']?(\w+)["\']?\s+.*?to\s+(\d+)', query, re.IGNORECASE)
        if update_match:
            update_column = update_match.group(1)
            update_value = update_match.group(2)
            params["columns"] = [update_column]
            params["update_values"] = [update_value]
        
        # Extract condition - look for patterns like "StudentID" 12345 or StudentID = 12345
        # Pattern: "ColumnName" VALUE or ColumnName = VALUE
        condition_patterns = [
            r'(?:with\s+)?["\']?(\w+ID)["\']?\s+(\d+)',  # "StudentID" 12345
            r'(?:where\s+)?["\']?(\w+ID)["\']?\s*=\s*(\d+)',  # StudentID = 12345
            r'student\s+with\s+["\']?(\w+)["\']?\s+(\d+)',  # student with "StudentID" 12345
        ]
        
        for pattern in condition_patterns:
            cond_match = re.search(pattern, query, re.IGNORECASE)
            if cond_match:
                cond_column = cond_match.group(1)
                cond_value = cond_match.group(2)
                params["conditions"] = [[f"{cond_column} = {cond_value}"]]
                break
    
    return {func_name: params}
