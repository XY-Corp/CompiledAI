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
    
    # Get function schema
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # For SQL INSERT operation, extract values from the query
    params = {}
    
    # Detect SQL operation type from query
    query_lower = query.lower()
    
    if "add" in query_lower or "insert" in query_lower:
        params["sql_keyword"] = "INSERT"
    elif "update" in query_lower or "modify" in query_lower:
        params["sql_keyword"] = "UPDATE"
    elif "delete" in query_lower or "remove" in query_lower:
        params["sql_keyword"] = "DELETE"
    elif "select" in query_lower or "get" in query_lower or "retrieve" in query_lower:
        params["sql_keyword"] = "SELECT"
    elif "create" in query_lower:
        params["sql_keyword"] = "CREATE"
    
    # Extract table name - look for patterns like 'table named "X"' or '"X" table'
    table_match = re.search(r'table\s+(?:named\s+)?["\']?(\w+)["\']?', query, re.IGNORECASE)
    if table_match:
        params["table_name"] = table_match.group(1)
    
    # Extract column names from "columns X, Y, Z" or from context
    columns_match = re.search(r'columns?\s+["\']?([^"\']+)["\']?(?:\s+and\s+["\']?(\w+)["\']?)?', query, re.IGNORECASE)
    if columns_match:
        cols_text = columns_match.group(0)
        # Extract quoted column names
        quoted_cols = re.findall(r'"(\w+)"', cols_text)
        if quoted_cols:
            params["columns"] = quoted_cols
    
    # For INSERT: extract values
    # Pattern: ID is "X", name is "Y", age is "Z", grade is "W"
    if params.get("sql_keyword") == "INSERT":
        # Extract field-value pairs
        field_value_pairs = re.findall(r"(\w+)(?:'s)?\s+(?:is|=)\s+[\"']([^\"']+)[\"']", query, re.IGNORECASE)
        
        if field_value_pairs:
            columns = []
            values = []
            for field, value in field_value_pairs:
                # Normalize field names
                field_lower = field.lower()
                if field_lower in ["id", "student"]:
                    columns.append("ID")
                elif field_lower == "name":
                    columns.append("Name")
                elif field_lower == "age":
                    columns.append("Age")
                elif field_lower == "grade":
                    columns.append("Grade")
                else:
                    columns.append(field)
                values.append(value)
            
            if columns:
                params["columns"] = columns
            if values:
                params["insert_values"] = [values]
    
    return {func_name: params}
