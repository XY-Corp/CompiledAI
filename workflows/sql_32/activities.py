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
    
    # Get function details
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    props = func.get("parameters", {}).get("properties", {})
    
    params = {}
    
    # Extract SQL keyword - look for CREATE, SELECT, INSERT, UPDATE, DELETE
    sql_keywords = ["CREATE", "SELECT", "INSERT", "UPDATE", "DELETE"]
    query_upper = query.upper()
    
    for kw in sql_keywords:
        if kw in query_upper or kw.lower() in query.lower():
            params["sql_keyword"] = kw
            break
    
    # If "create a new table" pattern found, it's CREATE
    if "create" in query.lower() and "table" in query.lower():
        params["sql_keyword"] = "CREATE"
    
    # Extract table name - look for patterns like 'table called "X"' or 'table named "X"'
    table_patterns = [
        r'table\s+(?:called|named)\s+["\']?([A-Za-z_][A-Za-z0-9_]*)["\']?',
        r'table\s+["\']([A-Za-z_][A-Za-z0-9_]*)["\']',
        r'into\s+(?:the\s+)?["\']?([A-Za-z_][A-Za-z0-9_]*)["\']?',
        r'from\s+(?:the\s+)?["\']?([A-Za-z_][A-Za-z0-9_]*)["\']?',
        r'update\s+(?:the\s+)?["\']?([A-Za-z_][A-Za-z0-9_]*)["\']?',
    ]
    
    for pattern in table_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            params["table_name"] = match.group(1)
            break
    
    # Extract column names - look for patterns with quoted column names
    # Pattern: columns named "X", "Y", "Z" or columns "X", "Y", "Z"
    columns_match = re.search(r'columns?\s+(?:named\s+)?(.+?)(?:\s+in\s+the|\s*\?|$)', query, re.IGNORECASE)
    if columns_match:
        columns_text = columns_match.group(1)
        # Extract quoted strings
        quoted_columns = re.findall(r'["\']([^"\']+)["\']', columns_text)
        if quoted_columns:
            params["columns"] = quoted_columns
    
    # Alternative: look for all quoted strings that look like column names
    if "columns" not in params:
        all_quoted = re.findall(r'["\']([A-Za-z_][A-Za-z0-9_]*)["\']', query)
        # Filter out the table name if we found it
        if "table_name" in params and all_quoted:
            columns = [c for c in all_quoted if c != params.get("table_name")]
            if columns:
                params["columns"] = columns
    
    # Extract conditions if present (WHERE clause patterns)
    conditions_match = re.search(r'where\s+(.+?)(?:\s*$|\s+order|\s+group|\s+limit)', query, re.IGNORECASE)
    if conditions_match:
        cond_text = conditions_match.group(1)
        # Split by AND/OR and format
        conditions = re.split(r'\s+and\s+|\s+or\s+', cond_text, flags=re.IGNORECASE)
        if conditions:
            params["conditions"] = [[c.strip() for c in conditions]]
    
    # Extract insert values if present
    values_match = re.search(r'values?\s*\((.+?)\)', query, re.IGNORECASE)
    if values_match:
        values_text = values_match.group(1)
        values = [v.strip().strip("'\"") for v in values_text.split(',')]
        if values:
            params["insert_values"] = [values]
    
    # Extract update values if present (SET clause)
    set_match = re.search(r'set\s+(.+?)(?:\s+where|\s*$)', query, re.IGNORECASE)
    if set_match:
        set_text = set_match.group(1)
        # Extract values from "col = val" patterns
        update_vals = re.findall(r'=\s*["\']?([^,\'"]+)["\']?', set_text)
        if update_vals:
            params["update_values"] = [v.strip() for v in update_vals]
    
    return {func_name: params}
