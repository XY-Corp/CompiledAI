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
    
    # Get function details
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters based on query content
    params = {}
    query_lower = query.lower()
    
    # Detect SQL operation type
    if "create" in query_lower or "establish" in query_lower or "new" in query_lower:
        params["sql_keyword"] = "CREATE"
    elif "select" in query_lower or "get" in query_lower or "retrieve" in query_lower or "fetch" in query_lower:
        params["sql_keyword"] = "SELECT"
    elif "insert" in query_lower or "add" in query_lower:
        params["sql_keyword"] = "INSERT"
    elif "update" in query_lower or "modify" in query_lower or "change" in query_lower:
        params["sql_keyword"] = "UPDATE"
    elif "delete" in query_lower or "remove" in query_lower:
        params["sql_keyword"] = "DELETE"
    
    # Extract table name - look for patterns like "table called X" or "table named X"
    table_patterns = [
        r'table\s+(?:called|named)\s+["\']?(\w+)["\']?',
        r'(?:database\s+)?table\s+["\']?(\w+)["\']?',
        r'(?:from|into|update)\s+["\']?(\w+)["\']?',
        r'["\'](\w+)["\']?\s+table',
    ]
    
    for pattern in table_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            params["table_name"] = match.group(1)
            break
    
    # Extract column names - look for quoted strings or field names
    # Pattern: "field1", "field2", etc. or fields X, Y, Z
    column_patterns = [
        r'(?:fields?|columns?)\s+(.+?)(?:\?|$)',
        r'with\s+(?:the\s+)?(?:fields?|columns?)\s+(.+?)(?:\?|$)',
    ]
    
    columns = []
    for pattern in column_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            fields_text = match.group(1)
            # Extract quoted strings
            quoted = re.findall(r'["\'](\w+)["\']', fields_text)
            if quoted:
                columns = quoted
            else:
                # Try comma/and separated words
                words = re.split(r',\s*|\s+and\s+', fields_text)
                columns = [w.strip().strip('"\'') for w in words if w.strip()]
            break
    
    if columns:
        params["columns"] = columns
    
    # Extract conditions if present (WHERE clause patterns)
    condition_patterns = [
        r'where\s+(.+?)(?:\?|$)',
        r'(?:if|when)\s+(.+?)(?:\?|$)',
    ]
    
    for pattern in condition_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            cond_text = match.group(1)
            # Parse conditions like "X = Y" or "X > Y"
            conditions = re.findall(r'(\w+\s*[=<>!]+\s*\w+)', cond_text)
            if conditions:
                params["conditions"] = [conditions]
            break
    
    # Extract values for INSERT if present
    values_match = re.search(r'values?\s*\((.+?)\)', query, re.IGNORECASE)
    if values_match:
        values_text = values_match.group(1)
        values = [v.strip().strip('"\'') for v in values_text.split(',')]
        params["insert_values"] = [values]
    
    return {func_name: params}
