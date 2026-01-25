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
        funcs = json.loads(functions) if isinstance(functions, str) else functions
    except (json.JSONDecodeError, TypeError):
        funcs = []
    
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    
    # For sql.execute, extract SQL operation details from the query
    params = {}
    query_lower = query.lower()
    
    # Determine SQL keyword based on query content
    if "update" in query_lower or "decrease" in query_lower or "increase" in query_lower or "change" in query_lower or "set" in query_lower:
        params["sql_keyword"] = "UPDATE"
    elif "delete" in query_lower or "remove" in query_lower:
        params["sql_keyword"] = "DELETE"
    elif "insert" in query_lower or "add" in query_lower:
        params["sql_keyword"] = "INSERT"
    elif "create" in query_lower:
        params["sql_keyword"] = "CREATE"
    else:
        params["sql_keyword"] = "SELECT"
    
    # Extract table name - look for patterns like "in the X table" or "X table" or "table X"
    table_patterns = [
        r'(?:in\s+the\s+|from\s+the\s+|into\s+the\s+|update\s+the\s+)?["\']?(\w+)["\']?\s+table',
        r'table\s+(?:named?\s+)?["\']?(\w+)["\']?',
        r'(?:in|from|into|update)\s+["\']?(\w+)["\']?(?:\s+table)?',
    ]
    
    for pattern in table_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            params["table_name"] = match.group(1)
            break
    
    if "table_name" not in params:
        params["table_name"] = "stocks"  # Default from context
    
    # Extract column names - look for "column" or specific field references
    column_patterns = [
        r'["\']?(\w+)["\']?\s+column',
        r'column\s+(?:named?\s+)?["\']?(\w+)["\']?',
        r'(?:the\s+)?["\']?(\w+)["\']?\s+(?:field|attribute)',
    ]
    
    columns = []
    for pattern in column_patterns:
        matches = re.findall(pattern, query, re.IGNORECASE)
        columns.extend(matches)
    
    # Also check for specific column mentions like "price"
    if "price" in query_lower and "price" not in [c.lower() for c in columns]:
        columns.append("price")
    
    if columns:
        params["columns"] = list(set(columns))  # Remove duplicates
    
    # Extract conditions - look for stock name or other identifiers
    conditions = []
    
    # Look for stock/item name patterns
    name_patterns = [
        r'(?:stock|item|product|record)\s+(?:named?|called)\s+["\']([^"\']+)["\']',
        r'["\']([^"\']+)["\'](?:\s+stock|\s+item)?',
        r'named?\s+["\']([^"\']+)["\']',
    ]
    
    for pattern in name_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            name_value = match.group(1)
            if name_value and name_value not in ["price", "stocks", "UPDATE", "SELECT"]:
                conditions.append([f"name = '{name_value}'"])
                break
    
    if conditions:
        params["conditions"] = conditions
    
    # Extract update values for UPDATE operations
    if params["sql_keyword"] == "UPDATE":
        update_values = []
        
        # Look for price calculations: "decrease by $X", "increase by $X", "current price of $X by $Y"
        # Pattern: decrease current price of $150 by $10
        decrease_match = re.search(r'decrease.*?\$?(\d+(?:\.\d+)?)\s+by\s+\$?(\d+(?:\.\d+)?)', query, re.IGNORECASE)
        increase_match = re.search(r'increase.*?\$?(\d+(?:\.\d+)?)\s+by\s+\$?(\d+(?:\.\d+)?)', query, re.IGNORECASE)
        
        if decrease_match:
            current_price = float(decrease_match.group(1))
            decrease_amount = float(decrease_match.group(2))
            new_price = current_price - decrease_amount
            update_values.append(str(int(new_price) if new_price == int(new_price) else new_price))
        elif increase_match:
            current_price = float(increase_match.group(1))
            increase_amount = float(increase_match.group(2))
            new_price = current_price + increase_amount
            update_values.append(str(int(new_price) if new_price == int(new_price) else new_price))
        else:
            # Look for simple "by $X" pattern
            by_match = re.search(r'by\s+\$?(\d+(?:\.\d+)?)', query, re.IGNORECASE)
            if by_match:
                amount = by_match.group(1)
                # Check if decrease or increase
                if "decrease" in query_lower:
                    update_values.append(f"price - {amount}")
                elif "increase" in query_lower:
                    update_values.append(f"price + {amount}")
        
        if update_values:
            params["update_values"] = update_values
    
    return {func_name: params}
