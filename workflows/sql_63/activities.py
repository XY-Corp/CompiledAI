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
    
    # Extract sql_keyword - look for SQL operation keywords
    if "sql_keyword" in props:
        if "create" in query_lower or "generate" in query_lower or "new" in query_lower:
            if "table" in query_lower:
                params["sql_keyword"] = "CREATE"
        elif "select" in query_lower or "get" in query_lower or "retrieve" in query_lower or "fetch" in query_lower:
            params["sql_keyword"] = "SELECT"
        elif "insert" in query_lower or "add" in query_lower:
            params["sql_keyword"] = "INSERT"
        elif "update" in query_lower or "modify" in query_lower or "change" in query_lower:
            params["sql_keyword"] = "UPDATE"
        elif "delete" in query_lower or "remove" in query_lower:
            params["sql_keyword"] = "DELETE"
    
    # Extract table_name - look for quoted table name or "named X" pattern
    if "table_name" in props:
        # Try quoted table name first
        table_match = re.search(r'(?:table\s+(?:named\s+)?|named\s+)["\']?([A-Za-z_][A-Za-z0-9_]*)["\']?', query, re.IGNORECASE)
        if table_match:
            params["table_name"] = table_match.group(1)
        else:
            # Try "table X" pattern
            table_match = re.search(r'table\s+([A-Za-z_][A-Za-z0-9_]*)', query, re.IGNORECASE)
            if table_match:
                params["table_name"] = table_match.group(1)
    
    # Extract columns - look for quoted column names or "columns X, Y, Z" pattern
    if "columns" in props:
        # Find all quoted strings that look like column names
        quoted_cols = re.findall(r'"([A-Za-z_][A-Za-z0-9_]*)"', query)
        
        # Filter out the table name if it was captured
        table_name = params.get("table_name", "")
        columns = [col for col in quoted_cols if col != table_name]
        
        if columns:
            params["columns"] = columns
        else:
            # Try "columns X, Y, Z" pattern
            cols_match = re.search(r'columns?\s+(.+?)(?:\s+to\s+|\s+for\s+|$)', query, re.IGNORECASE)
            if cols_match:
                cols_text = cols_match.group(1)
                # Split by comma or "and"
                cols = re.split(r',\s*|\s+and\s+', cols_text)
                columns = [col.strip().strip('"\'') for col in cols if col.strip()]
                if columns:
                    params["columns"] = columns
    
    # Only include non-empty params
    result_params = {k: v for k, v in params.items() if v}
    
    return {func_name: result_params}
