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
    
    # Detect SQL operation type
    if "sql_keyword" in props:
        if any(kw in query_lower for kw in ["update", "change", "adjust", "modify", "set"]):
            params["sql_keyword"] = "UPDATE"
        elif any(kw in query_lower for kw in ["select", "get", "fetch", "retrieve", "find", "show"]):
            params["sql_keyword"] = "SELECT"
        elif any(kw in query_lower for kw in ["insert", "add", "create new"]):
            params["sql_keyword"] = "INSERT"
        elif any(kw in query_lower for kw in ["delete", "remove"]):
            params["sql_keyword"] = "DELETE"
        elif "create" in query_lower and "table" in query_lower:
            params["sql_keyword"] = "CREATE"
    
    # Extract table name - look for patterns like "the X table" or "table X"
    if "table_name" in props:
        # Pattern: "the X table" or "X table"
        table_match = re.search(r'(?:the\s+)?["\']?(\w+)["\']?\s+table', query, re.IGNORECASE)
        if table_match:
            params["table_name"] = table_match.group(1)
        else:
            # Pattern: "table X" or "from X"
            table_match = re.search(r'(?:table|from)\s+["\']?(\w+)["\']?', query, re.IGNORECASE)
            if table_match:
                params["table_name"] = table_match.group(1)
    
    # Extract columns - look for "column" mentions
    if "columns" in props:
        # Pattern: "the X column" or "X column"
        col_matches = re.findall(r'(?:the\s+)?["\']?(\w+)["\']?\s+column', query, re.IGNORECASE)
        if col_matches:
            params["columns"] = col_matches
    
    # Extract update values - look for "to X" or "= X" patterns
    if "update_values" in props and params.get("sql_keyword") == "UPDATE":
        # Pattern: "to X" where X is a value (quoted or number)
        value_match = re.search(r'(?:to|=)\s+["\']?([^"\']+?)["\']?(?:\s+for|\s+where|\s*$)', query, re.IGNORECASE)
        if value_match:
            params["update_values"] = [value_match.group(1).strip()]
    
    # Extract conditions - look for "where X is Y" or "whose X is Y" patterns
    if "conditions" in props:
        conditions = []
        # Pattern: "whose X is Y" or "where X is Y" or "X = Y"
        cond_patterns = [
            r'(?:whose|where|if)\s+["\']?(\w+)["\']?\s+(?:is|=|equals)\s+["\']?([^"\']+?)["\']?(?:\s|$)',
            r'(?:whose|where|if)\s+["\']?(\w+)["\']?\s*=\s*["\']?([^"\']+?)["\']?(?:\s|$)',
        ]
        for pattern in cond_patterns:
            cond_matches = re.findall(pattern, query, re.IGNORECASE)
            for match in cond_matches:
                col_name = match[0]
                col_value = match[1].strip()
                conditions.append(f"{col_name} = {col_value}")
        
        if conditions:
            params["conditions"] = [conditions]
    
    return {func_name: params}
