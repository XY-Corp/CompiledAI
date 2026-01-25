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
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters based on the query content
    params = {}
    query_lower = query.lower()
    
    # Extract SQL keyword
    if "sql_keyword" in params_schema:
        # Look for SQL operation keywords in the query
        if any(word in query_lower for word in ["provide", "get", "show", "list", "names of", "find", "retrieve", "select"]):
            params["sql_keyword"] = "SELECT"
        elif "insert" in query_lower or "add" in query_lower:
            params["sql_keyword"] = "INSERT"
        elif "update" in query_lower or "modify" in query_lower or "change" in query_lower:
            params["sql_keyword"] = "UPDATE"
        elif "delete" in query_lower or "remove" in query_lower:
            params["sql_keyword"] = "DELETE"
        elif "create" in query_lower:
            params["sql_keyword"] = "CREATE"
        else:
            params["sql_keyword"] = "SELECT"  # Default for queries
    
    # Extract table name - look for patterns like "from the X table" or "X table"
    if "table_name" in params_schema:
        # Pattern: "from the \"TableName\" table" or "from \"TableName\" table"
        table_match = re.search(r'(?:from\s+(?:the\s+)?)?["\']([^"\']+)["\'](?:\s+table)?', query, re.IGNORECASE)
        if table_match:
            params["table_name"] = table_match.group(1)
        else:
            # Pattern: "from the TableName table" or "TableName table"
            table_match = re.search(r'(?:from\s+(?:the\s+)?)?(\w+)(?:_\w+)*\s+table', query, re.IGNORECASE)
            if table_match:
                params["table_name"] = table_match.group(1)
    
    # Extract column names - look for quoted column names or explicit mentions
    if "columns" in params_schema:
        # Pattern: find all quoted strings that look like column names
        # Look for "column_name" patterns
        column_matches = re.findall(r'["\'](\w+)["\']', query)
        
        # Filter out the table name from columns
        table_name = params.get("table_name", "")
        columns = [col for col in column_matches if col != table_name]
        
        if columns:
            params["columns"] = columns
    
    # Extract conditions - look for comparison patterns
    if "conditions" in params_schema:
        conditions = []
        
        # Pattern: "scored above X" -> "column > X"
        above_match = re.search(r'(?:scored?\s+)?above\s+(\d+)', query, re.IGNORECASE)
        if above_match:
            value = above_match.group(1)
            # Find the relevant column for the condition
            # Look for score-related column in the columns list
            score_col = None
            if "columns" in params:
                for col in params["columns"]:
                    if "score" in col.lower():
                        score_col = col
                        break
            if score_col:
                conditions.append([f"{score_col} > {value}"])
        
        # Pattern: "below X" or "less than X"
        below_match = re.search(r'(?:scored?\s+)?(?:below|less\s+than)\s+(\d+)', query, re.IGNORECASE)
        if below_match:
            value = below_match.group(1)
            score_col = None
            if "columns" in params:
                for col in params["columns"]:
                    if "score" in col.lower():
                        score_col = col
                        break
            if score_col:
                conditions.append([f"{score_col} < {value}"])
        
        # Pattern: "equal to X" or "equals X"
        equal_match = re.search(r'(?:equal(?:s)?\s+(?:to\s+)?|=\s*)(\d+)', query, re.IGNORECASE)
        if equal_match and not above_match and not below_match:
            value = equal_match.group(1)
            score_col = None
            if "columns" in params:
                for col in params["columns"]:
                    if "score" in col.lower():
                        score_col = col
                        break
            if score_col:
                conditions.append([f"{score_col} = {value}"])
        
        if conditions:
            params["conditions"] = conditions
    
    return {func_name: params}
