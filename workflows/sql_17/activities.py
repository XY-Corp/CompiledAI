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
    all relevant parameters like table name, conditions, etc.
    """
    # Parse prompt - handle BFCL format
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
        else:
            data = prompt
        
        # Extract user query from nested structure
        if "question" in data and isinstance(data["question"], list):
            if len(data["question"]) > 0 and isinstance(data["question"][0], list):
                query = data["question"][0][0].get("content", str(prompt))
            else:
                query = str(prompt)
        else:
            query = str(prompt)
    except (json.JSONDecodeError, TypeError, KeyError):
        query = str(prompt)
    
    # Parse functions
    if isinstance(functions, str):
        try:
            funcs = json.loads(functions)
        except json.JSONDecodeError:
            funcs = []
    else:
        funcs = functions if functions else []
    
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "sql.execute")
    
    query_lower = query.lower()
    
    # Determine SQL keyword based on query content
    sql_keyword = None
    if any(word in query_lower for word in ["delete", "remove", "eliminate", "drop record", "erase"]):
        sql_keyword = "DELETE"
    elif any(word in query_lower for word in ["insert", "add", "create record"]):
        sql_keyword = "INSERT"
    elif any(word in query_lower for word in ["update", "modify", "change", "set"]):
        sql_keyword = "UPDATE"
    elif any(word in query_lower for word in ["select", "fetch", "retrieve", "get", "find", "query"]):
        sql_keyword = "SELECT"
    elif "create" in query_lower and "table" in query_lower:
        sql_keyword = "CREATE"
    else:
        sql_keyword = "SELECT"  # Default
    
    # Extract table name - look for patterns like "table named X", "from X table", "X table"
    table_name = None
    table_patterns = [
        r'table\s+named\s+["\']?(\w+)["\']?',
        r'table\s+["\']?(\w+)["\']?',
        r'from\s+(?:the\s+)?["\']?(\w+)["\']?\s+table',
        r'["\'](\w+)["\']?\s+table',
        r'into\s+(?:the\s+)?["\']?(\w+)["\']?',
        r'update\s+(?:the\s+)?["\']?(\w+)["\']?',
    ]
    
    for pattern in table_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            table_name = match.group(1)
            break
    
    if not table_name:
        table_name = "unknown_table"
    
    # Extract conditions - look for WHERE-like patterns
    conditions = []
    
    # Pattern for conditions like "'ColumnName' equals 'Value'" or "ColumnName = Value"
    condition_patterns = [
        # 'Column' equals 'Value' or "Column" equals "Value"
        r"['\"](\w+)['\"]?\s+(?:equals?|=|is)\s+['\"]([^'\"]+)['\"]",
        # Column equals 'Value'
        r"(\w+)\s+(?:equals?|=|is)\s+['\"]([^'\"]+)['\"]",
        # where Column = Value
        r"where\s+['\"]?(\w+)['\"]?\s*(?:equals?|=)\s*['\"]?([^'\"]+)['\"]?",
    ]
    
    # Look for specific condition mentions
    # Pattern: 'ObservationID' of 'O789' or ObservationID of 'O789'
    of_pattern = r"['\"]?(\w+)['\"]?\s+of\s+['\"]([^'\"]+)['\"]"
    of_matches = re.findall(of_pattern, query)
    for col, val in of_matches:
        conditions.append([f"{col} = {val}"])
    
    # Also look for "equals" patterns
    equals_pattern = r"['\"](\w+)['\"]?\s+equals?\s+['\"]([^'\"]+)['\"]"
    equals_matches = re.findall(equals_pattern, query, re.IGNORECASE)
    for col, val in equals_matches:
        # Avoid duplicates
        cond_str = f"{col} = {val}"
        if [cond_str] not in conditions:
            conditions.append([cond_str])
    
    # Build result
    result = {
        "sql_keyword": sql_keyword,
        "table_name": table_name,
    }
    
    # Add conditions if found
    if conditions:
        result["conditions"] = conditions
    
    return {func_name: result}
