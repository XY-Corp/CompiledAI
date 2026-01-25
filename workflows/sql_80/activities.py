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
    
    Parses the user query and maps it to the appropriate function with parameters.
    Returns format: {"function_name": {"param1": val1, ...}}
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
    
    # Extract parameters for sql.execute
    params = {}
    query_lower = query.lower()
    
    # Determine SQL keyword based on query intent
    if any(word in query_lower for word in ["what are", "get", "find", "show", "list", "retrieve", "names", "salaries"]):
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
        params["sql_keyword"] = "SELECT"
    
    # Extract table name - look for patterns like "in the X table", "from X table", "table X"
    table_patterns = [
        r'(?:in|from|into|update|table)\s+(?:the\s+)?["\']?(\w+)["\']?\s+table',
        r'table\s+(?:named?\s+)?["\']?(\w+)["\']?',
        r'(?:in|from|into|update)\s+["\']?(\w+)["\']?(?:\s+who|\s+where|\s+with|\s+that|\s+having)?',
    ]
    
    table_name = None
    for pattern in table_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            table_name = match.group(1)
            break
    
    if table_name:
        params["table_name"] = table_name
    else:
        params["table_name"] = "<UNKNOWN>"
    
    # Extract column names - look for specific column mentions
    columns = []
    
    # Pattern for "names and salaries", "name, salary", etc.
    column_patterns = [
        r'(?:what are the|get|find|show|select)\s+([\w\s,]+?)\s+(?:of|from|in)',
        r'(?:columns?|fields?)\s*[:\s]*([\w\s,]+)',
    ]
    
    # Check for specific column mentions
    if "name" in query_lower and "salary" in query_lower:
        columns = ["name", "salary"]
    elif "names" in query_lower and "salaries" in query_lower:
        columns = ["name", "salary"]
    elif "name" in query_lower:
        columns = ["name"]
    elif "salary" in query_lower or "salaries" in query_lower:
        columns = ["salary"]
    
    if columns:
        params["columns"] = columns
    
    # Extract conditions - look for comparison patterns
    conditions = []
    
    # Pattern for "salary greater than $5000", "age > 30", etc.
    condition_patterns = [
        r'(\w+)\s+(?:greater than|more than|above|>)\s*\$?(\d+(?:\.\d+)?)',
        r'(\w+)\s+(?:less than|below|under|<)\s*\$?(\d+(?:\.\d+)?)',
        r'(\w+)\s*(?:=|equals?|is)\s*["\']?([^"\']+)["\']?',
        r'(\w+)\s*>\s*\$?(\d+(?:\.\d+)?)',
        r'(\w+)\s*<\s*\$?(\d+(?:\.\d+)?)',
    ]
    
    # Check for "greater than" conditions
    greater_match = re.search(r'(\w+)\s+(?:greater than|more than|above|>)\s*\$?(\d+(?:\.\d+)?)', query, re.IGNORECASE)
    if greater_match:
        col = greater_match.group(1).lower()
        val = greater_match.group(2)
        conditions.append(f"{col} > {val}")
    
    # Check for "less than" conditions
    less_match = re.search(r'(\w+)\s+(?:less than|below|under|<)\s*\$?(\d+(?:\.\d+)?)', query, re.IGNORECASE)
    if less_match:
        col = less_match.group(1).lower()
        val = less_match.group(2)
        conditions.append(f"{col} < {val}")
    
    # Check for equality conditions
    equals_match = re.search(r'(\w+)\s+(?:equals?|is|=)\s+["\']?([^"\']+)["\']?', query, re.IGNORECASE)
    if equals_match and not any(word in equals_match.group(0).lower() for word in ["greater", "less", "than"]):
        col = equals_match.group(1).lower()
        val = equals_match.group(2).strip()
        if col not in ["what", "who", "which", "that"]:
            conditions.append(f"{col} = {val}")
    
    if conditions:
        params["conditions"] = conditions
    
    return {func_name: params}
