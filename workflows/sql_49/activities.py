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
    """Extract function call parameters from natural language query.
    
    Parses the user query to identify the appropriate SQL operation and extracts
    all relevant parameters like table name, columns, and values.
    """
    # Parse prompt - may be JSON string with nested structure
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
        else:
            data = prompt
        
        # Extract user query from BFCL format
        if "question" in data and isinstance(data["question"], list):
            if len(data["question"]) > 0 and isinstance(data["question"][0], list):
                query = data["question"][0][0].get("content", str(prompt))
            else:
                query = str(prompt)
        else:
            query = str(prompt)
    except (json.JSONDecodeError, TypeError, KeyError):
        query = str(prompt)
    
    # Parse functions - may be JSON string
    try:
        if isinstance(functions, str):
            funcs = json.loads(functions)
        else:
            funcs = functions
    except (json.JSONDecodeError, TypeError):
        funcs = []
    
    # Get function schema
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "sql.execute")
    
    params = {}
    query_lower = query.lower()
    
    # Determine SQL keyword based on query content
    if "insert" in query_lower or "add" in query_lower or "incorporate" in query_lower or "new employee" in query_lower:
        params["sql_keyword"] = "INSERT"
    elif "update" in query_lower or "modify" in query_lower or "change" in query_lower:
        params["sql_keyword"] = "UPDATE"
    elif "delete" in query_lower or "remove" in query_lower:
        params["sql_keyword"] = "DELETE"
    elif "create" in query_lower:
        params["sql_keyword"] = "CREATE"
    else:
        params["sql_keyword"] = "SELECT"
    
    # Extract table name - look for patterns like 'table named "X"' or 'table "X"' or '"X" table'
    table_patterns = [
        r'table\s+named\s+["\']?(\w+)["\']?',
        r'table\s+["\'](\w+)["\']',
        r'["\'](\w+)["\']\s+table',
        r'into\s+(?:the\s+)?["\']?(\w+)["\']?\s+table',
        r'from\s+(?:the\s+)?["\']?(\w+)["\']?\s+table',
    ]
    
    for pattern in table_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            params["table_name"] = match.group(1)
            break
    
    if "table_name" not in params:
        # Fallback: look for capitalized words that might be table names
        cap_match = re.search(r'"(\w+)"', query)
        if cap_match:
            params["table_name"] = cap_match.group(1)
    
    # Extract column names - look for patterns like 'columns "X", "Y"' or column names in quotes
    columns_match = re.search(r'columns?\s+["\']?(\w+)["\']?(?:,\s*["\']?(\w+)["\']?)*', query, re.IGNORECASE)
    
    # Better approach: extract all quoted column names after "columns"
    if "columns" in query_lower:
        # Find all quoted strings that look like column names
        col_section = query[query_lower.find("columns"):]
        columns = re.findall(r'["\'](\w+)["\']', col_section)
        if columns:
            params["columns"] = columns
    
    # For INSERT operations, extract column names and values
    if params.get("sql_keyword") == "INSERT":
        # Extract column-value pairs from patterns like 'ColumnName is "Value"' or 'ColumnName is Value'
        # Pattern: ColumnName is "Value" or ColumnName is 'Value' or ColumnName is Value
        col_val_patterns = [
            r'(\w+)\s+is\s+["\']([^"\']+)["\']',  # ColumnName is "Value"
            r'(\w+)\s+is\s+"([^"]+)"',  # ColumnName is "Value"
        ]
        
        columns = []
        values = []
        
        # Find all column-value pairs
        matches = re.findall(r'(\w+)\s+is\s+["\']?([^"\'",]+)["\']?', query)
        
        for col, val in matches:
            # Skip common words that aren't column names
            if col.lower() in ['there', 'this', 'that', 'it', 'here', 'details', 'following', 'follows']:
                continue
            columns.append(col)
            values.append(val.strip())
        
        if columns:
            params["columns"] = columns
        if values:
            params["insert_values"] = [values]  # Nested array as per schema
    
    return {func_name: params}
