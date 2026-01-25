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
    
    # Extract parameters based on the query content
    params = {}
    query_lower = query.lower()
    
    # Extract SQL keyword
    if "sql_keyword" in params_schema:
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
    
    # Extract table name - look for patterns like 'table named "X"' or 'table "X"'
    if "table_name" in params_schema:
        # Pattern: table named "TableName" or table "TableName"
        table_match = re.search(r'table\s+(?:named\s+)?["\']?([A-Za-z_][A-Za-z0-9_]*)["\']?', query, re.IGNORECASE)
        if table_match:
            params["table_name"] = table_match.group(1)
    
    # Extract column names - look for patterns with quoted column names
    if "columns" in params_schema:
        # Find all quoted strings that look like column names
        # Pattern: "ColumnName" - extract all quoted strings
        quoted_strings = re.findall(r'"([^"]+)"', query)
        
        # Filter out the table name if present
        table_name = params.get("table_name", "")
        columns = [s for s in quoted_strings if s != table_name]
        
        if columns:
            params["columns"] = columns
    
    return {func_name: params}
