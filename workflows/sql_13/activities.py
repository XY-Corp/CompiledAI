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
    
    # Get function schema
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters based on the query content
    params = {}
    query_lower = query.lower()
    
    # For sql.execute function - extract SQL operation details
    if func_name == "sql.execute":
        # Determine SQL keyword
        if "create" in query_lower or "establish" in query_lower or "new database table" in query_lower:
            params["sql_keyword"] = "CREATE"
        elif "select" in query_lower or "retrieve" in query_lower or "get" in query_lower or "fetch" in query_lower:
            params["sql_keyword"] = "SELECT"
        elif "insert" in query_lower or "add" in query_lower:
            params["sql_keyword"] = "INSERT"
        elif "update" in query_lower or "modify" in query_lower:
            params["sql_keyword"] = "UPDATE"
        elif "delete" in query_lower or "remove" in query_lower:
            params["sql_keyword"] = "DELETE"
        
        # Extract table name - look for patterns like 'table called "X"' or 'table named "X"'
        table_patterns = [
            r'table\s+(?:called|named)\s+["\']?([A-Za-z_][A-Za-z0-9_]*)["\']?',
            r'table\s+["\']([A-Za-z_][A-Za-z0-9_]*)["\']',
            r'["\']([A-Za-z_][A-Za-z0-9_]*)["\']?\s+table',
            r'from\s+["\']?([A-Za-z_][A-Za-z0-9_]*)["\']?',
            r'into\s+["\']?([A-Za-z_][A-Za-z0-9_]*)["\']?',
        ]
        
        for pattern in table_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                params["table_name"] = match.group(1)
                break
        
        # Extract column names - look for patterns with quoted column names
        # Pattern: columns "Col1", "Col2", "Col3" or columns Col1, Col2, Col3
        columns_match = re.search(r'(?:columns?|with\s+the\s+columns?)\s+(.+?)(?:\s+to\s+record|\s+for|\s*$)', query, re.IGNORECASE)
        if columns_match:
            columns_text = columns_match.group(1)
            # Extract quoted column names
            quoted_columns = re.findall(r'["\']([^"\']+)["\']', columns_text)
            if quoted_columns:
                params["columns"] = quoted_columns
            else:
                # Try unquoted comma-separated
                unquoted = re.findall(r'([A-Za-z_][A-Za-z0-9_]*)', columns_text)
                if unquoted:
                    params["columns"] = unquoted
        
        # Extract conditions if present (for SELECT, UPDATE, DELETE)
        conditions_match = re.search(r'where\s+(.+?)(?:\s*$|\s+order|\s+group|\s+limit)', query, re.IGNORECASE)
        if conditions_match:
            cond_text = conditions_match.group(1)
            # Parse conditions like "col1 = val1 and col2 > val2"
            conds = re.split(r'\s+and\s+', cond_text, flags=re.IGNORECASE)
            if conds:
                params["conditions"] = [[c.strip()] for c in conds]
        
        # Extract values for INSERT
        if params.get("sql_keyword") == "INSERT":
            values_match = re.search(r'values?\s*\((.+?)\)', query, re.IGNORECASE)
            if values_match:
                values_text = values_match.group(1)
                values = [v.strip().strip("'\"") for v in values_text.split(',')]
                params["insert_values"] = [values]
        
        # Extract values for UPDATE
        if params.get("sql_keyword") == "UPDATE":
            set_match = re.search(r'set\s+(.+?)(?:\s+where|\s*$)', query, re.IGNORECASE)
            if set_match:
                set_text = set_match.group(1)
                # Parse "col1 = val1, col2 = val2"
                assignments = re.findall(r'(\w+)\s*=\s*["\']?([^,\'"]+)["\']?', set_text)
                if assignments:
                    params["update_values"] = [a[1].strip() for a in assignments]
    
    return {func_name: params}
