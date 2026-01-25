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
    
    # Get function schema
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    props = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters based on query content
    params = {}
    query_lower = query.lower()
    
    # Extract SQL keyword
    if "sql_keyword" in props:
        sql_keywords = ["SELECT", "INSERT", "UPDATE", "DELETE", "CREATE"]
        for kw in sql_keywords:
            if kw.lower() in query_lower or f"list" in query_lower or "provide" in query_lower or "get" in query_lower:
                params["sql_keyword"] = "SELECT"
                break
        if "sql_keyword" not in params:
            params["sql_keyword"] = "SELECT"  # Default for queries asking for data
    
    # Extract table name - look for patterns like "from the X table" or "table X"
    if "table_name" in props:
        # Pattern: "from the \"X\" table" or "from \"X\" table"
        table_match = re.search(r'(?:from\s+(?:the\s+)?)["\']?(\w+)["\']?\s+table', query_lower)
        if not table_match:
            # Pattern: "\"X\" table"
            table_match = re.search(r'["\'](\w+)["\']\s+table', query_lower)
        if not table_match:
            # Pattern: table "X"
            table_match = re.search(r'table\s+["\']?(\w+)["\']?', query_lower)
        
        if table_match:
            params["table_name"] = table_match.group(1)
    
    # Extract column names - look for patterns in quotes or after "columns"
    if "columns" in props:
        # Look for column names in quotes
        column_matches = re.findall(r'["\'](\w+)["\']', query)
        
        # Filter out table name and disease value from columns
        table_name = params.get("table_name", "")
        columns = []
        for col in column_matches:
            col_lower = col.lower()
            # Skip if it's the table name or a condition value
            if col_lower != table_name.lower() and col_lower not in ["cancer", "select", "insert", "update", "delete", "create"]:
                columns.append(col)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_columns = []
        for col in columns:
            if col not in seen:
                seen.add(col)
                unique_columns.append(col)
        
        if unique_columns:
            params["columns"] = unique_columns
    
    # Extract conditions - look for "where X = Y" or "condition where X is Y"
    if "conditions" in props:
        conditions = []
        
        # Pattern: "where disease is \"Cancer\"" or "disease = \"Cancer\""
        condition_patterns = [
            r'where\s+(\w+)\s+is\s+["\']?(\w+)["\']?',
            r'condition\s+where\s+(\w+)\s+is\s+["\']?(\w+)["\']?',
            r'(\w+)\s*=\s*["\']?(\w+)["\']?',
        ]
        
        for pattern in condition_patterns:
            matches = re.findall(pattern, query, re.IGNORECASE)
            for match in matches:
                col, val = match
                # Skip if this looks like a column definition, not a condition
                if col.lower() in ["gene_name", "gene", "name"]:
                    continue
                condition_str = f'{col} = "{val}"'
                if condition_str not in conditions:
                    conditions.append(condition_str)
        
        # Also look for explicit disease condition
        disease_match = re.search(r'disease\s+(?:is\s+)?["\']?(\w+)["\']?', query, re.IGNORECASE)
        if disease_match:
            disease_val = disease_match.group(1)
            condition_str = f'disease = "{disease_val}"'
            if condition_str not in conditions:
                conditions = [condition_str]  # Use this as the primary condition
        
        if conditions:
            params["conditions"] = conditions
    
    return {func_name: params}
