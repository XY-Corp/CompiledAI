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
    
    Parses the user query to identify SQL operation details and returns
    the function name with extracted parameters.
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
    
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "sql.execute")
    
    # Extract SQL parameters from query using regex and string matching
    params = {}
    query_lower = query.lower()
    
    # Extract SQL keyword
    if "name" in query_lower or "what is" in query_lower or "get" in query_lower or "find" in query_lower:
        params["sql_keyword"] = "SELECT"
    elif "insert" in query_lower or "add" in query_lower:
        params["sql_keyword"] = "INSERT"
    elif "update" in query_lower or "change" in query_lower or "modify" in query_lower:
        params["sql_keyword"] = "UPDATE"
    elif "delete" in query_lower or "remove" in query_lower:
        params["sql_keyword"] = "DELETE"
    elif "create" in query_lower:
        params["sql_keyword"] = "CREATE"
    else:
        params["sql_keyword"] = "SELECT"
    
    # Extract table name - look for patterns like "in the 'table' table" or "'table' table"
    table_patterns = [
        r"(?:in|from|into|update)\s+(?:the\s+)?['\"]?(\w+)['\"]?\s+table",
        r"['\"](\w+)['\"]?\s+table",
        r"table\s+['\"]?(\w+)['\"]?",
        r"from\s+['\"]?(\w+)['\"]?",
    ]
    
    for pattern in table_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            params["table_name"] = match.group(1)
            break
    
    if "table_name" not in params:
        params["table_name"] = "table"
    
    # Extract columns - look for patterns like "columns 'col1' and 'col2'" or "the columns 'id' and 'name'"
    columns_patterns = [
        r"columns?\s+['\"]?(\w+)['\"]?\s+and\s+['\"]?(\w+)['\"]?",
        r"columns?\s+['\"]?(\w+)['\"]?,\s*['\"]?(\w+)['\"]?",
        r"consider(?:ing)?\s+(?:the\s+)?columns?\s+['\"]?(\w+)['\"]?\s+and\s+['\"]?(\w+)['\"]?",
    ]
    
    columns = []
    for pattern in columns_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            columns = [match.group(1), match.group(2)]
            break
    
    # Also check for single column mentions
    if not columns:
        single_col_match = re.findall(r"column\s+['\"]?(\w+)['\"]?", query, re.IGNORECASE)
        if single_col_match:
            columns = single_col_match
    
    if columns:
        params["columns"] = columns
    
    # Extract conditions - look for patterns like "condition 'x = y'" or "where x = y"
    condition_patterns = [
        r"condition\s+['\"]?(\w+\s*=\s*\w+)['\"]?",
        r"where\s+['\"]?(\w+\s*=\s*\w+)['\"]?",
        r"(?:condition|where)\s+['\"]?(\w+)\s*=\s*['\"]?(\w+)['\"]?",
    ]
    
    conditions = []
    for pattern in condition_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            if len(match.groups()) == 2:
                conditions = [[f"{match.group(1)} = {match.group(2)}"]]
            else:
                # Clean up the condition
                cond = match.group(1).strip()
                # Normalize spacing around operators
                cond = re.sub(r'\s*=\s*', ' = ', cond)
                conditions = [[cond]]
            break
    
    # Also look for ID patterns like "ID 1234" or "id = 1234"
    if not conditions:
        id_match = re.search(r"(?:ID|id)\s*[=]?\s*(\d+)", query)
        if id_match:
            conditions = [[f"id = {id_match.group(1)}"]]
    
    if conditions:
        params["conditions"] = conditions
    
    return {func_name: params}
