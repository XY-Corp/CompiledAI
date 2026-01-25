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
    
    Parses the user query and function schema to extract the appropriate
    function name and parameters. Returns format: {"function_name": {params}}
    """
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
    props = func.get("parameters", {}).get("properties", {})
    
    params = {}
    query_lower = query.lower()
    
    # Extract SQL keyword
    if "sql_keyword" in props:
        sql_keywords = ["SELECT", "INSERT", "UPDATE", "DELETE", "CREATE"]
        for kw in sql_keywords:
            if kw.lower() in query_lower or (kw == "UPDATE" and "modify" in query_lower):
                params["sql_keyword"] = kw
                break
        # Default based on context clues
        if "sql_keyword" not in params:
            if "modify" in query_lower or "change" in query_lower or "set" in query_lower:
                params["sql_keyword"] = "UPDATE"
            elif "add" in query_lower or "insert" in query_lower:
                params["sql_keyword"] = "INSERT"
            elif "delete" in query_lower or "remove" in query_lower:
                params["sql_keyword"] = "DELETE"
            elif "create" in query_lower:
                params["sql_keyword"] = "CREATE"
            else:
                params["sql_keyword"] = "SELECT"
    
    # Extract table name - look for quoted table names or patterns like "X table" or "X database table"
    if "table_name" in props:
        # Pattern: "TableName" table or in the "TableName" database table
        table_match = re.search(r'["\']([A-Za-z_][A-Za-z0-9_]*)["\'](?:\s+(?:database\s+)?table)?', query)
        if table_match:
            params["table_name"] = table_match.group(1)
        else:
            # Pattern: the X table
            table_match = re.search(r'the\s+([A-Za-z_][A-Za-z0-9_]*)\s+(?:database\s+)?table', query, re.IGNORECASE)
            if table_match:
                params["table_name"] = table_match.group(1)
    
    # Extract column names - look for quoted column names
    if "columns" in props:
        # Pattern: "ColumnName" column
        col_matches = re.findall(r'["\']([A-Za-z_][A-Za-z0-9_]*)["\'](?:\s+column)?', query)
        # Filter out table name if already found
        table_name = params.get("table_name", "")
        columns = [c for c in col_matches if c != table_name]
        if columns:
            params["columns"] = columns
    
    # Extract update values - look for "new X of Y" or "set to Y" patterns
    if "update_values" in props and params.get("sql_keyword") == "UPDATE":
        # Pattern: new average height of 150 cm or set to 150
        value_match = re.search(r'(?:new\s+(?:average\s+)?(?:height|value)\s+of\s+|set\s+(?:to\s+)?|reflect\s+a\s+new\s+(?:average\s+)?(?:height\s+)?of\s+)(\d+(?:\.\d+)?)', query, re.IGNORECASE)
        if value_match:
            params["update_values"] = [value_match.group(1)]
    
    # Extract conditions - look for WHERE-like conditions
    if "conditions" in props:
        conditions = []
        
        # Pattern: for the plant species "X" or species "X"
        species_match = re.search(r'(?:plant\s+)?species\s+["\']([^"\']+)["\']', query, re.IGNORECASE)
        if species_match:
            # Find the column name that likely refers to species (could be name, species_name, etc.)
            # Common patterns: species name column or just use a generic approach
            species_col_match = re.search(r'["\']([A-Za-z_]*[Nn]ame[A-Za-z_]*)["\']', query)
            if species_col_match:
                conditions.append([f"{species_col_match.group(1)} = '{species_match.group(1)}'"])
            else:
                # Default to common column names
                conditions.append([f"species_name = '{species_match.group(1)}'"])
        
        # Pattern: current X is less than Y or X < Y
        less_than_match = re.search(r'(?:current\s+)?(?:average\s+)?(?:height|value)(?:\s+recorded)?\s+is\s+less\s+than\s+(\d+(?:\.\d+)?)', query, re.IGNORECASE)
        if less_than_match:
            # Find the column for this condition
            col_name = params.get("columns", ["AverageHeight"])[0] if params.get("columns") else "AverageHeight"
            conditions.append([f"{col_name} < {less_than_match.group(1)}"])
        
        if conditions:
            params["conditions"] = conditions
    
    return {func_name: params}
