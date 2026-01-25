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
    query_lower = query.lower()
    
    # Determine SQL keyword based on action words in query
    if "sql_keyword" in props:
        if any(word in query_lower for word in ["delete", "eliminate", "remove", "drop data"]):
            params["sql_keyword"] = "DELETE"
        elif any(word in query_lower for word in ["insert", "add", "create new"]):
            params["sql_keyword"] = "INSERT"
        elif any(word in query_lower for word in ["update", "modify", "change", "set"]):
            params["sql_keyword"] = "UPDATE"
        elif any(word in query_lower for word in ["select", "get", "fetch", "retrieve", "find", "show"]):
            params["sql_keyword"] = "SELECT"
        elif any(word in query_lower for word in ["create table", "create"]):
            params["sql_keyword"] = "CREATE"
    
    # Extract table name - look for patterns like "from X table", "the X table", "table X"
    if "table_name" in props:
        # Pattern: "X" table or table "X" or from "X"
        table_patterns = [
            r'["\']([^"\']+)["\']\s*table',  # "TableName" table
            r'table\s*["\']([^"\']+)["\']',  # table "TableName"
            r'from\s+(?:the\s+)?["\']?([A-Za-z_][A-Za-z0-9_]*)["\']?',  # from TableName
            r'(?:in|into|from)\s+(?:the\s+)?["\']?([A-Za-z_][A-Za-z0-9_]*)["\']?\s+table',  # in/into the X table
        ]
        for pattern in table_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                params["table_name"] = match.group(1)
                break
    
    # Extract conditions - look for WHERE-like conditions
    if "conditions" in props:
        # Pattern: where/when/if "ColumnName" is/equals/= "Value"
        condition_patterns = [
            r'(?:where|when|if)\s+(?:the\s+)?["\']?([A-Za-z_][A-Za-z0-9_]*)["\']?\s+(?:is|equals?|=)\s+["\']([^"\']+)["\']',
            r'["\']([A-Za-z_][A-Za-z0-9_]*)["\']?\s+(?:is|equals?|=)\s+["\']([^"\']+)["\']',
        ]
        conditions = []
        for pattern in condition_patterns:
            matches = re.findall(pattern, query, re.IGNORECASE)
            for match in matches:
                col_name, value = match
                conditions.append([f"{col_name} = '{value}'"])
                break  # Take first match
            if conditions:
                break
        
        if conditions:
            params["conditions"] = conditions
    
    # Extract columns if mentioned
    if "columns" in props:
        # Look for column names in quotes or specific patterns
        col_pattern = r'column[s]?\s+["\']?([A-Za-z_][A-Za-z0-9_]*(?:\s*,\s*[A-Za-z_][A-Za-z0-9_]*)*)["\']?'
        match = re.search(col_pattern, query, re.IGNORECASE)
        if match:
            cols = [c.strip() for c in match.group(1).split(',')]
            params["columns"] = cols
    
    # Extract insert_values if INSERT operation
    if "insert_values" in props and params.get("sql_keyword") == "INSERT":
        # Look for values in parentheses or after "values"
        values_pattern = r'values?\s*\(([^)]+)\)'
        match = re.search(values_pattern, query, re.IGNORECASE)
        if match:
            values = [v.strip().strip("'\"") for v in match.group(1).split(',')]
            params["insert_values"] = [values]
    
    # Extract update_values if UPDATE operation
    if "update_values" in props and params.get("sql_keyword") == "UPDATE":
        # Look for "set X to Y" or "X = Y" patterns
        set_pattern = r'set\s+["\']?([A-Za-z_][A-Za-z0-9_]*)["\']?\s+(?:to|=)\s+["\']?([^"\']+)["\']?'
        matches = re.findall(set_pattern, query, re.IGNORECASE)
        if matches:
            params["update_values"] = [m[1] for m in matches]
    
    return {func_name: params}
