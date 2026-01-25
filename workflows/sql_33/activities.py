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
    
    # Extract sql_keyword - look for SQL operation keywords
    if "sql_keyword" in props:
        if "create" in query_lower or "generate" in query_lower or "new table" in query_lower:
            params["sql_keyword"] = "CREATE"
        elif "select" in query_lower or "get" in query_lower or "fetch" in query_lower or "retrieve" in query_lower:
            params["sql_keyword"] = "SELECT"
        elif "insert" in query_lower or "add" in query_lower:
            params["sql_keyword"] = "INSERT"
        elif "update" in query_lower or "modify" in query_lower or "change" in query_lower:
            params["sql_keyword"] = "UPDATE"
        elif "delete" in query_lower or "remove" in query_lower:
            params["sql_keyword"] = "DELETE"
    
    # Extract table_name - look for patterns like "table named X" or "table X"
    if "table_name" in props:
        # Pattern: table named "X" or table named 'X'
        table_match = re.search(r'table\s+named\s+["\']?([^"\']+)["\']?', query, re.IGNORECASE)
        if not table_match:
            # Pattern: table "X" or table 'X'
            table_match = re.search(r'table\s+["\']([^"\']+)["\']', query, re.IGNORECASE)
        if not table_match:
            # Pattern: into X table or from X table
            table_match = re.search(r'(?:into|from|in)\s+(?:the\s+)?["\']?(\w+)["\']?\s+table', query, re.IGNORECASE)
        if not table_match:
            # Pattern: table X (word after table)
            table_match = re.search(r'table\s+(\w+)', query, re.IGNORECASE)
        
        if table_match:
            params["table_name"] = table_match.group(1).strip('"\'')
    
    # Extract columns - look for column names in quotes or after "columns"
    if "columns" in props:
        # Pattern: column names being "X", "Y", "Z" or columns "X", "Y"
        # Find all quoted strings that look like column names
        quoted_columns = re.findall(r'["\']([^"\']+)["\']', query)
        
        # Filter out the table name if it was captured
        table_name = params.get("table_name", "")
        columns = [col for col in quoted_columns if col != table_name]
        
        if columns:
            params["columns"] = columns
    
    # Extract conditions if present
    if "conditions" in props:
        # Look for WHERE-like conditions: field = value, field > value, etc.
        condition_patterns = re.findall(r'(\w+)\s*(=|>|<|>=|<=|!=)\s*["\']?([^"\']+)["\']?', query)
        if condition_patterns:
            conditions = [f"{field} {op} {val}" for field, op, val in condition_patterns]
            params["conditions"] = conditions
    
    # Extract insert_values if present (for INSERT operations)
    if "insert_values" in props and params.get("sql_keyword") == "INSERT":
        # Look for values in parentheses or after "values"
        values_match = re.search(r'values?\s*\(([^)]+)\)', query, re.IGNORECASE)
        if values_match:
            values = [v.strip().strip('"\'') for v in values_match.group(1).split(',')]
            params["insert_values"] = [values]
    
    # Extract update_values if present (for UPDATE operations)
    if "update_values" in props and params.get("sql_keyword") == "UPDATE":
        # Look for SET clause patterns: field = value
        set_patterns = re.findall(r'set\s+(\w+)\s*=\s*["\']?([^"\']+)["\']?', query, re.IGNORECASE)
        if set_patterns:
            params["update_values"] = [val for _, val in set_patterns]
    
    return {func_name: params}
