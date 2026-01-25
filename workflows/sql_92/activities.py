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
    
    # Get function details
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    props = func.get("parameters", {}).get("properties", {})
    
    params = {}
    query_lower = query.lower()
    
    # Extract SQL keyword
    if "sql_keyword" in props:
        sql_keywords = ["SELECT", "INSERT", "UPDATE", "DELETE", "CREATE"]
        for kw in sql_keywords:
            if kw.lower() in query_lower:
                params["sql_keyword"] = kw
                break
    
    # Extract table name - look for patterns like "table named X" or "table X"
    if "table_name" in props:
        # Pattern: "table named "X"" or "table named 'X'" or "table named X"
        table_match = re.search(r'table\s+named\s+["\']?(\w+)["\']?', query, re.IGNORECASE)
        if not table_match:
            # Pattern: "table "X"" or "table 'X'"
            table_match = re.search(r'table\s+["\'](\w+)["\']', query, re.IGNORECASE)
        if not table_match:
            # Pattern: "into X" for INSERT
            table_match = re.search(r'into\s+["\']?(\w+)["\']?', query, re.IGNORECASE)
        if not table_match:
            # Pattern: "from X" for SELECT
            table_match = re.search(r'from\s+["\']?(\w+)["\']?', query, re.IGNORECASE)
        if table_match:
            params["table_name"] = table_match.group(1)
    
    # Extract column names - look for patterns with quoted column names
    if "columns" in props:
        # Find all quoted strings that look like column names
        # Pattern: "ColumnName" - find all quoted identifiers
        column_matches = re.findall(r'"(\w+)"', query)
        
        # Filter out the table name if it was captured
        table_name = params.get("table_name", "")
        columns = [col for col in column_matches if col.lower() != table_name.lower()]
        
        if columns:
            params["columns"] = columns
    
    # Extract conditions if present (for WHERE clauses)
    if "conditions" in props:
        # Look for condition patterns like "where X = Y" or "X > Y"
        condition_patterns = [
            r'where\s+(\w+)\s*(=|>|<|>=|<=|!=)\s*["\']?(\w+)["\']?',
            r'(\w+)\s*(=|>|<|>=|<=|!=)\s*["\']?(\w+)["\']?\s+(?:and|or)',
        ]
        conditions = []
        for pattern in condition_patterns:
            matches = re.findall(pattern, query, re.IGNORECASE)
            for match in matches:
                if len(match) >= 3:
                    conditions.append(f"{match[0]} {match[1]} {match[2]}")
        if conditions:
            params["conditions"] = conditions
    
    # Extract insert_values if INSERT operation
    if "insert_values" in props and params.get("sql_keyword") == "INSERT":
        # Look for values in parentheses after VALUES keyword
        values_match = re.search(r'values?\s*\(([^)]+)\)', query, re.IGNORECASE)
        if values_match:
            values_str = values_match.group(1)
            values = [v.strip().strip("'\"") for v in values_str.split(',')]
            params["insert_values"] = [values]
    
    # Extract update_values if UPDATE operation
    if "update_values" in props and params.get("sql_keyword") == "UPDATE":
        # Look for SET clause values
        set_match = re.search(r'set\s+(.+?)(?:\s+where|$)', query, re.IGNORECASE)
        if set_match:
            set_clause = set_match.group(1)
            # Extract values from "col = val" patterns
            value_matches = re.findall(r'=\s*["\']?(\w+)["\']?', set_clause)
            if value_matches:
                params["update_values"] = value_matches
    
    return {func_name: params}
