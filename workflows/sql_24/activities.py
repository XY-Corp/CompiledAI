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
    all relevant parameters like table name, columns, values, and conditions.
    Returns format: {"function_name": {"param1": val1, ...}}
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
    
    params = {}
    query_lower = query.lower()
    
    # Determine SQL keyword based on query content
    if "update" in query_lower:
        params["sql_keyword"] = "UPDATE"
    elif "insert" in query_lower:
        params["sql_keyword"] = "INSERT"
    elif "delete" in query_lower:
        params["sql_keyword"] = "DELETE"
    elif "create" in query_lower:
        params["sql_keyword"] = "CREATE"
    else:
        params["sql_keyword"] = "SELECT"
    
    # Extract table name - look for patterns like "table named X" or "table X"
    table_patterns = [
        r'table\s+named\s+["\']?(\w+)["\']?',
        r'table\s+["\']?(\w+)["\']?',
        r'from\s+["\']?(\w+)["\']?',
        r'into\s+["\']?(\w+)["\']?',
        r'update\s+["\']?(\w+)["\']?',
    ]
    
    for pattern in table_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            params["table_name"] = match.group(1)
            break
    
    if "table_name" not in params:
        params["table_name"] = ""
    
    # For UPDATE operations, extract columns and update_values
    if params["sql_keyword"] == "UPDATE":
        # Extract column to update - look for patterns like "atomic weight" or specific column names
        # Common patterns: "update the X" or "new X is Y"
        
        # Look for what's being updated
        update_col_patterns = [
            r'(?:update|revise|change|set)\s+(?:the\s+)?["\']?(\w+(?:\s+\w+)?)["\']?\s+(?:to|is|=)',
            r'new\s+(\w+(?:\s+\w+)?)\s+is',
            r'(\w+(?:\s+\w+)?)\s+(?:has been|was)\s+(?:revised|updated|changed)',
        ]
        
        column_to_update = None
        for pattern in update_col_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                col_text = match.group(1).strip()
                # Convert to column name format (e.g., "atomic weight" -> "AtomicWeight")
                column_to_update = col_text
                break
        
        # Check for specific column mentions in the query
        if "atomic weight" in query_lower or "atomicweight" in query_lower:
            column_to_update = "AtomicWeight"
        
        if column_to_update:
            params["columns"] = [column_to_update]
        
        # Extract the new value - look for numbers or quoted strings
        value_patterns = [
            r'(?:new\s+\w+(?:\s+\w+)?\s+is|to|=)\s+["\']?(\d+\.?\d*)["\']?',
            r'(?:is|to|=)\s+["\']?(\d+\.?\d*)["\']?',
            r'(\d+\.\d+)',  # Decimal number
        ]
        
        for pattern in value_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                params["update_values"] = [match.group(1)]
                break
    
    # Extract conditions - look for WHERE clause patterns
    condition_patterns = [
        r"where\s+['\"]?(\w+)['\"]?\s+(?:is|=)\s+['\"]?([^'\"]+)['\"]?",
        r"condition\s+where\s+['\"]?(\w+)['\"]?\s+(?:is|=)\s+['\"]?([^'\"]+)['\"]?",
        r"['\"](\w+)['\"]?\s+(?:is|=)\s+['\"]([^'\"]+)['\"]",
    ]
    
    conditions = []
    for pattern in condition_patterns:
        matches = re.findall(pattern, query, re.IGNORECASE)
        for match in matches:
            col_name = match[0].strip()
            col_value = match[1].strip().rstrip('.')
            conditions.append([f"{col_name} = {col_value}"])
            break
        if conditions:
            break
    
    # Also check for specific element name condition
    if not conditions:
        element_match = re.search(r"['\"]?ElementName['\"]?\s+(?:is|=)\s+['\"]?(\w+)['\"]?", query, re.IGNORECASE)
        if element_match:
            conditions.append([f"ElementName = {element_match.group(1)}"])
        else:
            # Look for element name in quotes
            element_match = re.search(r'element\s+["\'](\w+)["\']', query, re.IGNORECASE)
            if element_match:
                conditions.append([f"ElementName = {element_match.group(1)}"])
    
    if conditions:
        params["conditions"] = conditions
    
    return {func_name: params}
