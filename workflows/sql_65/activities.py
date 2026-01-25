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
    
    Parses the user query and available function schema to extract
    the appropriate function name and parameters.
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
    
    params = {}
    query_lower = query.lower()
    
    # Extract SQL keyword based on action words in query
    if "sql_keyword" in props:
        if any(word in query_lower for word in ["modify", "update", "change", "set"]):
            params["sql_keyword"] = "UPDATE"
        elif any(word in query_lower for word in ["select", "get", "fetch", "retrieve", "find"]):
            params["sql_keyword"] = "SELECT"
        elif any(word in query_lower for word in ["insert", "add", "create new"]):
            params["sql_keyword"] = "INSERT"
        elif any(word in query_lower for word in ["delete", "remove"]):
            params["sql_keyword"] = "DELETE"
        elif "create" in query_lower and "table" in query_lower:
            params["sql_keyword"] = "CREATE"
    
    # Extract table name - look for patterns like "table called X" or "table named X"
    if "table_name" in props:
        table_patterns = [
            r'table\s+(?:called|named)\s+["\']?(\w+)["\']?',
            r'(?:from|into|update|in)\s+["\']?(\w+)["\']?\s+table',
            r'table\s+["\']?(\w+)["\']?',
        ]
        for pattern in table_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                params["table_name"] = match.group(1)
                break
    
    # Extract columns - look for column names in quotes
    if "columns" in props:
        # For UPDATE, extract the column being modified
        col_patterns = [
            r'(?:modify|update|change|set)\s+(?:the\s+)?["\']?(\w+)["\']?\s+column',
            r'["\'](\w+)["\']?\s+column',
            r'column\s+["\']?(\w+)["\']?',
        ]
        columns = []
        for pattern in col_patterns:
            matches = re.findall(pattern, query, re.IGNORECASE)
            if matches:
                columns.extend(matches)
                break
        if columns:
            params["columns"] = columns
    
    # Extract update values - look for "to 'value'" or "= 'value'"
    if "update_values" in props and params.get("sql_keyword") == "UPDATE":
        value_patterns = [
            r"to\s+['\"]([^'\"]+)['\"]",
            r"=\s*['\"]([^'\"]+)['\"]",
        ]
        for pattern in value_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                params["update_values"] = [match.group(1)]
                break
    
    # Extract conditions - look for WHERE-like conditions
    if "conditions" in props:
        conditions = []
        
        # Pattern for "column is/= 'value'" or "column is above/below/greater/less X"
        condition_patterns = [
            # Age above/greater than X
            r"['\"]?(\w+)['\"]?\s+(?:is\s+)?(?:above|greater\s+than|>)\s+(\d+)",
            # Column = 'value' or is 'value'
            r"['\"]?(\w+)['\"]?\s+(?:is|=)\s+['\"]([^'\"]+)['\"]",
        ]
        
        for pattern in condition_patterns:
            matches = re.findall(pattern, query, re.IGNORECASE)
            for match in matches:
                col, val = match
                # Determine operator
                if re.search(rf"{col}\s+(?:is\s+)?(?:above|greater)", query, re.IGNORECASE):
                    conditions.append(f"{col} > {val}")
                else:
                    conditions.append(f"{col} = '{val}'")
        
        if conditions:
            params["conditions"] = [conditions]
    
    return {func_name: params}
