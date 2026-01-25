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
            if "question" in data and isinstance(data["question"], list):
                query = data["question"][0][0].get("content", prompt) if data["question"] and data["question"][0] else prompt
            else:
                query = str(prompt)
        else:
            query = str(prompt)
    except (json.JSONDecodeError, TypeError, IndexError, KeyError):
        query = str(prompt)
    
    # Parse functions (may be JSON string)
    try:
        if isinstance(functions, str):
            funcs = json.loads(functions)
        else:
            funcs = functions
    except json.JSONDecodeError:
        funcs = []
    
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    props = func.get("parameters", {}).get("properties", {})
    
    query_lower = query.lower()
    params = {}
    
    # Extract sql_keyword based on action words in query
    if "sql_keyword" in props:
        if any(word in query_lower for word in ["remove", "delete", "drop records"]):
            params["sql_keyword"] = "DELETE"
        elif any(word in query_lower for word in ["insert", "add", "create record"]):
            params["sql_keyword"] = "INSERT"
        elif any(word in query_lower for word in ["update", "modify", "change", "set"]):
            params["sql_keyword"] = "UPDATE"
        elif any(word in query_lower for word in ["select", "get", "fetch", "retrieve", "find", "show"]):
            params["sql_keyword"] = "SELECT"
        elif any(word in query_lower for word in ["create table", "create database"]):
            params["sql_keyword"] = "CREATE"
    
    # Extract table_name - look for patterns like "table named X", "table X", "from X"
    if "table_name" in props:
        table_patterns = [
            r'table\s+named\s+["\']?(\w+)["\']?',
            r'table\s+["\']?(\w+)["\']?',
            r'from\s+["\']?(\w+)["\']?',
            r'into\s+["\']?(\w+)["\']?',
        ]
        for pattern in table_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                params["table_name"] = match.group(1)
                break
    
    # Extract columns - look for column names in quotes or after "columns"
    if "columns" in props:
        # Look for quoted column names
        quoted_cols = re.findall(r'["\'](\w+)["\']', query)
        # Filter out table name if present
        table_name = params.get("table_name", "").lower()
        columns = [col for col in quoted_cols if col.lower() != table_name]
        
        # Also check for "columns X, Y, Z" pattern
        col_match = re.search(r'columns?\s+(?:are\s+)?(?:involved\s+)?(?:in\s+)?(?:this\s+)?(?:operation\s+)?(?:are\s+)?["\']?(\w+)["\']?,?\s*["\']?(\w+)["\']?,?\s*(?:and\s+)?["\']?(\w+)["\']?', query, re.IGNORECASE)
        if col_match:
            columns = [g for g in col_match.groups() if g]
        
        if columns:
            params["columns"] = columns
    
    # Extract conditions - look for comparison patterns like "GPA less than 2.0"
    if "conditions" in props:
        conditions = []
        
        # Pattern: "X less than Y" or "X < Y"
        less_than = re.search(r'["\']?(\w+)["\']?\s+(?:less\s+than|<)\s+(\d+\.?\d*)', query, re.IGNORECASE)
        if less_than:
            conditions.append([f"{less_than.group(1)} < {less_than.group(2)}"])
        
        # Pattern: "X greater than Y" or "X > Y"
        greater_than = re.search(r'["\']?(\w+)["\']?\s+(?:greater\s+than|>)\s+(\d+\.?\d*)', query, re.IGNORECASE)
        if greater_than:
            conditions.append([f"{greater_than.group(1)} > {greater_than.group(2)}"])
        
        # Pattern: "X equal to Y" or "X = Y"
        equal_to = re.search(r'["\']?(\w+)["\']?\s+(?:equal\s+to|=|equals)\s+["\']?(\w+\.?\d*)["\']?', query, re.IGNORECASE)
        if equal_to:
            conditions.append([f"{equal_to.group(1)} = {equal_to.group(2)}"])
        
        if conditions:
            params["conditions"] = conditions
    
    return {func_name: params}
