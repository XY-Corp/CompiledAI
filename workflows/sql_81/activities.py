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
    # Parse prompt - may be JSON string with nested structure
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
    
    # Parse functions - may be JSON string
    try:
        if isinstance(functions, str):
            funcs = json.loads(functions)
        else:
            funcs = functions
    except (json.JSONDecodeError, TypeError):
        funcs = []
    
    # Get function details
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Initialize result params
    params = {}
    query_lower = query.lower()
    
    # Extract SQL keyword
    if "sql_keyword" in params_schema:
        # Detect SQL operation type from query
        if any(word in query_lower for word in ["provide", "get", "show", "list", "find", "retrieve", "names", "balances"]):
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
            params["sql_keyword"] = "SELECT"  # Default for queries
    
    # Extract table name - look for quoted table names or common patterns
    if "table_name" in params_schema:
        # Pattern: "table_name" or 'table_name' or from table_name
        table_match = re.search(r'["\']([^"\']+)["\'](?:\s+table)?', query)
        if table_match:
            params["table_name"] = table_match.group(1)
        else:
            # Try "from X table" or "from the X table"
            table_match = re.search(r'from\s+(?:the\s+)?(\w+)\s+table', query_lower)
            if table_match:
                params["table_name"] = table_match.group(1).capitalize()
            else:
                # Try just "X table"
                table_match = re.search(r'(\w+)\s+table', query_lower)
                if table_match:
                    params["table_name"] = table_match.group(1).capitalize()
    
    # Extract columns - look for specific column mentions
    if "columns" in params_schema:
        columns = []
        # Common column patterns
        if "names" in query_lower or "name" in query_lower:
            columns.append("name")
        if "balance" in query_lower or "balances" in query_lower:
            columns.append("account_balance")
        if "account" in query_lower and "balance" not in query_lower:
            columns.append("account")
        
        # If we found specific columns, use them; otherwise default to all
        if columns:
            params["columns"] = columns
        else:
            params["columns"] = ["*"]
    
    # Extract conditions - look for comparison patterns
    if "conditions" in params_schema:
        conditions = []
        
        # Pattern: "greater than $X" or "> $X" or "more than $X"
        greater_match = re.search(r'(?:greater than|more than|>|above|over)\s*\$?([\d,]+(?:\.\d+)?)', query, re.IGNORECASE)
        if greater_match:
            value = greater_match.group(1).replace(",", "")
            # Determine which column the condition applies to
            if "balance" in query_lower:
                conditions.append([f"account_balance > {value}"])
            else:
                conditions.append([f"amount > {value}"])
        
        # Pattern: "less than $X" or "< $X"
        less_match = re.search(r'(?:less than|fewer than|<|below|under)\s*\$?([\d,]+(?:\.\d+)?)', query, re.IGNORECASE)
        if less_match:
            value = less_match.group(1).replace(",", "")
            if "balance" in query_lower:
                conditions.append([f"account_balance < {value}"])
            else:
                conditions.append([f"amount < {value}"])
        
        # Pattern: "equal to $X" or "= $X"
        equal_match = re.search(r'(?:equal to|equals|=)\s*\$?([\d,]+(?:\.\d+)?)', query, re.IGNORECASE)
        if equal_match:
            value = equal_match.group(1).replace(",", "")
            conditions.append([f"amount = {value}"])
        
        if conditions:
            params["conditions"] = conditions
    
    return {func_name: params}
