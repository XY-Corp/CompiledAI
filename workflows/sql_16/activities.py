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
            if "question" in data and isinstance(data["question"], list):
                query = data["question"][0][0].get("content", prompt) if data["question"] and data["question"][0] else prompt
            else:
                query = prompt
        else:
            data = prompt
            if "question" in data and isinstance(data["question"], list):
                query = data["question"][0][0].get("content", str(prompt)) if data["question"] and data["question"][0] else str(prompt)
            else:
                query = str(prompt)
    except (json.JSONDecodeError, KeyError, IndexError, TypeError):
        query = str(prompt)
    
    # Parse functions
    if isinstance(functions, str):
        try:
            functions = json.loads(functions)
        except json.JSONDecodeError:
            functions = []
    
    func = functions[0] if functions else {}
    func_name = func.get("name", "sql.execute")
    
    # Extract SQL keyword based on intent
    query_lower = query.lower()
    sql_keyword = None
    
    if any(word in query_lower for word in ["remove", "delete", "drop row", "eliminate"]):
        sql_keyword = "DELETE"
    elif any(word in query_lower for word in ["insert", "add", "create row"]):
        sql_keyword = "INSERT"
    elif any(word in query_lower for word in ["update", "modify", "change", "set"]):
        sql_keyword = "UPDATE"
    elif any(word in query_lower for word in ["select", "get", "fetch", "retrieve", "find", "query"]):
        sql_keyword = "SELECT"
    elif "create" in query_lower and "table" in query_lower:
        sql_keyword = "CREATE"
    else:
        sql_keyword = "SELECT"  # default
    
    # Extract table name - look for patterns like "table named X", "from X table", etc.
    table_name = None
    table_patterns = [
        r'table\s+named\s+["\']?(\w+)["\']?',
        r'table\s+["\'](\w+)["\']',
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
    
    # Extract conditions - look for equality conditions
    conditions = []
    
    # Pattern for conditions like "'ColumnName' equals 'Value'" or "ColumnName = Value"
    condition_patterns = [
        r"['\"]?(\w+)['\"]?\s+(?:equals?|=)\s+['\"]?(\w+)['\"]?",
        r"where\s+['\"]?(\w+)['\"]?\s*=\s*['\"]?(\w+)['\"]?",
    ]
    
    # Find all conditions mentioned
    for pattern in condition_patterns:
        matches = re.findall(pattern, query, re.IGNORECASE)
        for match in matches:
            col, val = match
            # Skip if this looks like a table name reference
            if col.lower() in ["table", "named", "the"]:
                continue
            condition_str = f"{col} = '{val}'"
            if condition_str not in conditions:
                conditions.append(condition_str)
    
    # Also look for specific ID patterns like "MeasurementID' of 'M123'"
    id_pattern = r"['\"]?(\w+ID)['\"]?\s+(?:of|equals?|=|is)\s+['\"]?(\w+)['\"]?"
    id_matches = re.findall(id_pattern, query, re.IGNORECASE)
    for match in id_matches:
        col, val = match
        condition_str = f"{col} = '{val}'"
        if condition_str not in conditions:
            conditions.append(condition_str)
    
    # Build result with only required/relevant parameters
    params = {
        "sql_keyword": sql_keyword,
        "table_name": table_name or "unknown_table",
    }
    
    # Add conditions if present (as nested array per schema)
    if conditions:
        params["conditions"] = [conditions]
    
    return {func_name: params}
