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
            if kw.lower() in query_lower or (kw == "UPDATE" and "modify" in query_lower) or (kw == "UPDATE" and "setting" in query_lower):
                params["sql_keyword"] = kw
                break
        # Check for modify/set patterns which indicate UPDATE
        if "sql_keyword" not in params:
            if any(word in query_lower for word in ["modify", "set", "change", "update"]):
                params["sql_keyword"] = "UPDATE"
    
    # Extract table name - look for patterns like "the X table" or "table X"
    if "table_name" in props:
        # Pattern: "the \"X\" table" or "\"X\" table"
        table_match = re.search(r'["\'](\w+)["\'][\s]+table', query, re.IGNORECASE)
        if not table_match:
            # Pattern: "table \"X\""
            table_match = re.search(r'table[\s]+["\'](\w+)["\']', query, re.IGNORECASE)
        if not table_match:
            # Pattern: "the X table" without quotes
            table_match = re.search(r'the[\s]+(\w+)[\s]+table', query, re.IGNORECASE)
        if table_match:
            params["table_name"] = table_match.group(1)
    
    # Extract columns - look for "column" or "columns" patterns
    if "columns" in props:
        # Pattern: "the \"X\" column" or setting "X" column
        col_matches = re.findall(r'["\'](\w+)["\'][\s]+column', query, re.IGNORECASE)
        if col_matches:
            params["columns"] = col_matches
    
    # Extract update values - look for "to X" or "= X" patterns after column
    if "update_values" in props:
        # Pattern: "to \"X\"" or "to X"
        update_match = re.search(r'(?:to|=)[\s]+["\']?(\w+)["\']?', query, re.IGNORECASE)
        if update_match:
            params["update_values"] = [update_match.group(1)]
    
    # Extract conditions - look for "where", "whose", "for all X where Y"
    if "conditions" in props:
        conditions = []
        # Pattern: "whose \"X\" is \"Y\"" or "where \"X\" = \"Y\""
        cond_match = re.search(r'(?:whose|where|for\s+all\s+\w+\s+whose)[\s]+["\']?(\w+)["\']?[\s]+(?:is|=|equals)[\s]+["\']?(\w+)["\']?', query, re.IGNORECASE)
        if cond_match:
            col_name = cond_match.group(1)
            col_value = cond_match.group(2)
            conditions.append([f"{col_name} = {col_value}"])
        
        if conditions:
            params["conditions"] = conditions
    
    return {func_name: params}
