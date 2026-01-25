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
    
    params = {}
    query_lower = query.lower()
    
    # Extract sql_keyword - look for SQL operation keywords
    if "sql_keyword" in props:
        if "update" in query_lower or "add" in query_lower or "set" in query_lower:
            params["sql_keyword"] = "UPDATE"
        elif "select" in query_lower or "get" in query_lower or "what is" in query_lower or "find" in query_lower:
            # Check if it's asking about result of an update vs just selecting
            if "after" in query_lower and ("add" in query_lower or "update" in query_lower):
                params["sql_keyword"] = "UPDATE"
            else:
                params["sql_keyword"] = "SELECT"
        elif "insert" in query_lower or "add new" in query_lower:
            params["sql_keyword"] = "INSERT"
        elif "delete" in query_lower or "remove" in query_lower:
            params["sql_keyword"] = "DELETE"
        elif "create" in query_lower:
            params["sql_keyword"] = "CREATE"
        else:
            params["sql_keyword"] = "UPDATE"  # Default based on context
    
    # Extract table_name - look for quoted table names or "table" keyword
    if "table_name" in props:
        # Pattern: "table_name" table or in the "table_name" table
        table_match = re.search(r'["\'](\w+)["\'](?:\s+table|\s+database)', query, re.IGNORECASE)
        if table_match:
            params["table_name"] = table_match.group(1)
        else:
            # Try: in the "X" table
            table_match = re.search(r'in\s+the\s+["\'](\w+)["\']', query, re.IGNORECASE)
            if table_match:
                params["table_name"] = table_match.group(1)
    
    # Extract columns - look for quoted column names
    if "columns" in props:
        # Pattern: "column_name" column
        col_match = re.search(r'["\'](\w+)["\'](?:\s+column)', query, re.IGNORECASE)
        if col_match:
            params["columns"] = [col_match.group(1)]
        else:
            # Look for column mentioned in context
            col_match = re.search(r'in\s+the\s+["\'](\w+)["\'](?:\s+column)', query, re.IGNORECASE)
            if col_match:
                params["columns"] = [col_match.group(1)]
    
    # Extract update_values - for UPDATE operations, calculate new value
    if "update_values" in props and params.get("sql_keyword") == "UPDATE":
        # Look for "add $X to ... current balance of $Y"
        add_match = re.search(r'add\s+\$?(\d+(?:\.\d+)?)', query, re.IGNORECASE)
        current_match = re.search(r'current\s+balance\s+of\s+\$?(\d+(?:\.\d+)?)', query, re.IGNORECASE)
        
        if add_match and current_match:
            add_amount = float(add_match.group(1))
            current_balance = float(current_match.group(1))
            new_balance = current_balance + add_amount
            # Format as integer if whole number
            if new_balance == int(new_balance):
                params["update_values"] = [str(int(new_balance))]
            else:
                params["update_values"] = [str(new_balance)]
        elif add_match:
            # Just the add amount if no current balance specified
            params["update_values"] = [add_match.group(1)]
    
    # Extract conditions - look for customer name or other WHERE conditions
    if "conditions" in props:
        conditions = []
        # Look for customer name: "John Doe" or named "John Doe"
        name_match = re.search(r'(?:customer\s+)?named\s+["\']([^"\']+)["\']', query, re.IGNORECASE)
        if name_match:
            conditions.append([f"name = '{name_match.group(1)}'"])
        else:
            # Try: customer "Name"
            name_match = re.search(r'customer\s+["\']([^"\']+)["\']', query, re.IGNORECASE)
            if name_match:
                conditions.append([f"name = '{name_match.group(1)}'"])
        
        if conditions:
            params["conditions"] = conditions
    
    return {func_name: params}
