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
    
    # Extract SQL keyword - look for operation type in query
    if "sql_keyword" in props:
        query_lower = query.lower()
        if "delete" in query_lower or "remove" in query_lower:
            params["sql_keyword"] = "DELETE"
        elif "insert" in query_lower or "add" in query_lower:
            params["sql_keyword"] = "INSERT"
        elif "update" in query_lower or "modify" in query_lower or "change" in query_lower:
            params["sql_keyword"] = "UPDATE"
        elif "create" in query_lower:
            params["sql_keyword"] = "CREATE"
        else:
            params["sql_keyword"] = "SELECT"
    
    # Extract table name - look for quoted table name or "from/into/table X"
    if "table_name" in props:
        # Try quoted table name first (e.g., "Genes")
        table_match = re.search(r'["\']([^"\']+)["\'](?:\s+table|\s+where|\s+record)', query, re.IGNORECASE)
        if table_match:
            params["table_name"] = table_match.group(1)
        else:
            # Try "from X table" or "the X table" pattern
            table_match = re.search(r'(?:from|into|the)\s+["\']?([A-Za-z_][A-Za-z0-9_]*)["\']?\s+table', query, re.IGNORECASE)
            if table_match:
                params["table_name"] = table_match.group(1)
            else:
                # Try "X table" pattern
                table_match = re.search(r'["\']([A-Za-z_][A-Za-z0-9_]*)["\']', query)
                if table_match:
                    params["table_name"] = table_match.group(1)
    
    # Extract conditions - look for "where X is/= Y" patterns
    if "conditions" in props:
        conditions = []
        # Pattern: "ColumnName" is "Value" or ColumnName = Value
        cond_patterns = [
            r'["\']([A-Za-z_][A-Za-z0-9_]*)["\'](?:\s+is|\s*=)\s*["\']([^"\']+)["\']',
            r'where\s+(?:the\s+)?["\']?([A-Za-z_][A-Za-z0-9_]*)["\']?\s+(?:is|=)\s*["\']?([^"\']+)["\']?',
        ]
        
        for pattern in cond_patterns:
            matches = re.findall(pattern, query, re.IGNORECASE)
            for match in matches:
                col_name = match[0]
                value = match[1].strip('"\'')
                conditions.append([f"{col_name} = '{value}'"])
        
        if conditions:
            params["conditions"] = conditions
    
    return {func_name: params}
