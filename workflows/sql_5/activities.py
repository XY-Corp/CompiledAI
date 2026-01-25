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
    """Extract function call parameters from natural language query about SQL operations."""
    
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
    
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "sql.execute")
    
    query_lower = query.lower()
    params = {}
    
    # Determine SQL keyword based on query content
    if "modify" in query_lower or "update" in query_lower or "change" in query_lower or "set" in query_lower:
        params["sql_keyword"] = "UPDATE"
    elif "insert" in query_lower or "add" in query_lower:
        params["sql_keyword"] = "INSERT"
    elif "delete" in query_lower or "remove" in query_lower:
        params["sql_keyword"] = "DELETE"
    elif "create" in query_lower:
        params["sql_keyword"] = "CREATE"
    else:
        params["sql_keyword"] = "SELECT"
    
    # Extract table name - look for patterns like "table called X" or "table named X"
    table_patterns = [
        r'table\s+(?:called|named)\s+["\']?(\w+)["\']?',
        r'(?:from|into|update)\s+["\']?(\w+)["\']?',
        r'table\s+["\']?(\w+)["\']?',
    ]
    
    for pattern in table_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            params["table_name"] = match.group(1)
            break
    
    if "table_name" not in params:
        params["table_name"] = ""
    
    # Extract column names mentioned in the query
    # Look for column patterns like "column named X" or quoted column names
    column_patterns = [
        r'["\'](\w+Score)["\']',
        r'["\'](\w+ID)["\']',
        r'columns?\s+(?:named|called)\s+["\']?(\w+)["\']?',
    ]
    
    columns = []
    for pattern in column_patterns:
        matches = re.findall(pattern, query, re.IGNORECASE)
        columns.extend(matches)
    
    # For UPDATE operations, extract the column being modified
    if params["sql_keyword"] == "UPDATE":
        # Look for "modify the X" or "change the X" or "set X to"
        modify_patterns = [
            r'modify\s+(?:the\s+)?["\']?(\w+)["\']?\s+(?:of|to)',
            r'change\s+(?:the\s+)?["\']?(\w+)["\']?\s+(?:of|to)',
            r'set\s+(?:the\s+)?["\']?(\w+)["\']?\s+to',
        ]
        
        update_column = None
        for pattern in modify_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                update_column = match.group(1)
                break
        
        if update_column:
            params["columns"] = [update_column]
        elif columns:
            # Filter to find the column being updated (not the ID column)
            non_id_columns = [c for c in columns if "ID" not in c]
            if non_id_columns:
                params["columns"] = [non_id_columns[0]]
            else:
                params["columns"] = columns[:1]
        
        # Extract update value - look for "to X" patterns with numbers
        update_value_patterns = [
            r'to\s+(\d+)',
            r'=\s*(\d+)',
            r'value\s+(?:of\s+)?(\d+)',
        ]
        
        for pattern in update_value_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                params["update_values"] = [match.group(1)]
                break
        
        # Extract conditions - look for ID values and conditions
        # Pattern: "ExamID" 67890 or ExamID = 67890
        condition_patterns = [
            r'["\']?(\w+ID)["\']?\s+(\d+)',
            r'["\']?(\w+ID)["\']?\s*=\s*(\d+)',
            r'with\s+["\']?(\w+)["\']?\s+(\d+)',
        ]
        
        for pattern in condition_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                col_name = match.group(1)
                col_value = match.group(2)
                params["conditions"] = [[f"{col_name} = {col_value}"]]
                break
    
    return {func_name: params}
