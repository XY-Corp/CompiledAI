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
        if "create" in query_lower:
            params["sql_keyword"] = "CREATE"
        elif "select" in query_lower:
            params["sql_keyword"] = "SELECT"
        elif "insert" in query_lower:
            params["sql_keyword"] = "INSERT"
        elif "update" in query_lower:
            params["sql_keyword"] = "UPDATE"
        elif "delete" in query_lower:
            params["sql_keyword"] = "DELETE"
    
    # Extract table_name - look for patterns like 'table named "X"' or 'table "X"'
    if "table_name" in props:
        # Pattern: table named "TableName" or table "TableName"
        table_match = re.search(r'table\s+(?:named\s+)?["\']?([A-Za-z_][A-Za-z0-9_]*)["\']?', query, re.IGNORECASE)
        if table_match:
            params["table_name"] = table_match.group(1)
    
    # Extract columns - look for column names in quotes
    if "columns" in props:
        # Pattern: columns "Col1", "Col2", ... or with columns "Col1", "Col2"
        # Find all quoted strings that look like column names
        column_matches = re.findall(r'"([A-Za-z_][A-Za-z0-9_]*)"', query)
        
        # Filter out the table name from columns
        table_name = params.get("table_name", "")
        columns = [col for col in column_matches if col != table_name]
        
        if columns:
            params["columns"] = columns
    
    # Extract conditions if present (for WHERE clauses)
    if "conditions" in props:
        # Look for condition patterns like "where X = Y" or "condition X > Y"
        cond_match = re.search(r'where\s+(.+?)(?:\s+and\s+|\s*$)', query, re.IGNORECASE)
        if cond_match:
            conditions = [cond_match.group(1).strip()]
            params["conditions"] = conditions
    
    # Extract insert_values if present
    if "insert_values" in props:
        # Look for values in parentheses or after "values"
        values_match = re.search(r'values?\s*\(([^)]+)\)', query, re.IGNORECASE)
        if values_match:
            values = [v.strip().strip('"\'') for v in values_match.group(1).split(',')]
            params["insert_values"] = [values]
    
    # Extract update_values if present
    if "update_values" in props:
        # Look for SET clause patterns
        set_match = re.search(r'set\s+(.+?)(?:\s+where|\s*$)', query, re.IGNORECASE)
        if set_match:
            # Parse "col1 = val1, col2 = val2"
            assignments = set_match.group(1).split(',')
            values = []
            for assignment in assignments:
                if '=' in assignment:
                    val = assignment.split('=')[1].strip().strip('"\'')
                    values.append(val)
            if values:
                params["update_values"] = values
    
    return {func_name: params}
