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
            # Extract user query from BFCL format
            if "question" in data and isinstance(data["question"], list):
                if len(data["question"]) > 0 and isinstance(data["question"][0], list):
                    query = data["question"][0][0].get("content", prompt)
                elif len(data["question"]) > 0 and isinstance(data["question"][0], dict):
                    query = data["question"][0].get("content", prompt)
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
    
    # Get function details
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    props = func.get("parameters", {}).get("properties", {})
    
    params = {}
    query_lower = query.lower()
    
    # Extract sql_keyword based on query content
    if "sql_keyword" in props:
        if "create" in query_lower or "form a new table" in query_lower or "new table" in query_lower:
            params["sql_keyword"] = "CREATE"
        elif "select" in query_lower or "get" in query_lower or "retrieve" in query_lower or "fetch" in query_lower:
            params["sql_keyword"] = "SELECT"
        elif "insert" in query_lower or "add" in query_lower:
            params["sql_keyword"] = "INSERT"
        elif "update" in query_lower or "modify" in query_lower or "change" in query_lower:
            params["sql_keyword"] = "UPDATE"
        elif "delete" in query_lower or "remove" in query_lower:
            params["sql_keyword"] = "DELETE"
    
    # Extract table_name - look for quoted table name or "table called X" pattern
    if "table_name" in props:
        # Try quoted table name first
        table_match = re.search(r'(?:table\s+(?:called|named)?\s*)?["\']([^"\']+)["\']', query)
        if table_match:
            params["table_name"] = table_match.group(1)
        else:
            # Try "table called X" or "table X" pattern
            table_match = re.search(r'table\s+(?:called|named)?\s*(\w+)', query, re.IGNORECASE)
            if table_match:
                params["table_name"] = table_match.group(1)
    
    # Extract columns - look for quoted column names
    if "columns" in props:
        # Find all quoted strings that look like column names
        # Pattern: "ColumnName" - look for quoted strings after "columns" or "with"
        column_matches = re.findall(r'"([^"]+)"', query)
        
        if column_matches:
            # Filter out the table name if it was captured
            table_name = params.get("table_name", "")
            columns = [col for col in column_matches if col != table_name]
            if columns:
                params["columns"] = columns
    
    # Extract insert_values if present
    if "insert_values" in props:
        # Look for values in parentheses or after "values"
        values_match = re.search(r'values?\s*\(([^)]+)\)', query, re.IGNORECASE)
        if values_match:
            values_str = values_match.group(1)
            values = [v.strip().strip("'\"") for v in values_str.split(",")]
            params["insert_values"] = [values]
    
    # Extract update_values if present
    if "update_values" in props:
        # Look for "set X = Y" patterns
        set_matches = re.findall(r'set\s+(\w+)\s*=\s*["\']?([^"\']+)["\']?', query, re.IGNORECASE)
        if set_matches:
            params["update_values"] = [match[1] for match in set_matches]
    
    # Extract conditions if present
    if "conditions" in props:
        # Look for WHERE clause or condition patterns
        where_match = re.search(r'where\s+(.+?)(?:$|order|group|limit)', query, re.IGNORECASE)
        if where_match:
            conditions_str = where_match.group(1)
            # Split by AND/OR
            conditions = re.split(r'\s+and\s+|\s+or\s+', conditions_str, flags=re.IGNORECASE)
            params["conditions"] = [[cond.strip()] for cond in conditions if cond.strip()]
    
    return {func_name: params}
