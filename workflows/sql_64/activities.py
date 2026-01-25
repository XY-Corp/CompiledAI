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
    """Extract function call parameters from user query using regex and string matching."""
    
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
    
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    props = func.get("parameters", {}).get("properties", {})
    
    query_lower = query.lower()
    params = {}
    
    # For sql.execute function, extract SQL operation details
    if func_name == "sql.execute":
        # Determine SQL keyword based on query content
        if any(word in query_lower for word in ["change", "update", "set", "modify"]):
            params["sql_keyword"] = "UPDATE"
        elif any(word in query_lower for word in ["select", "get", "retrieve", "fetch", "find"]):
            params["sql_keyword"] = "SELECT"
        elif any(word in query_lower for word in ["insert", "add", "create new"]):
            params["sql_keyword"] = "INSERT"
        elif any(word in query_lower for word in ["delete", "remove"]):
            params["sql_keyword"] = "DELETE"
        elif "create" in query_lower and "table" in query_lower:
            params["sql_keyword"] = "CREATE"
        
        # Extract table name - look for patterns like "table named X" or "table X"
        table_patterns = [
            r'table\s+named\s+["\']?(\w+)["\']?',
            r'table\s+["\']?(\w+)["\']?',
            r'in\s+["\']?(\w+)["\']?\s+table',
            r'from\s+["\']?(\w+)["\']?',
        ]
        for pattern in table_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                params["table_name"] = match.group(1)
                break
        
        # Extract column names - look for quoted column names or patterns like "the X column"
        column_patterns = [
            r'["\'](\w+)["\']\s+column',
            r'column\s+["\']?(\w+)["\']?',
            r'the\s+["\']?(\w+)["\']?\s+(?:column|field)',
        ]
        columns = []
        for pattern in column_patterns:
            matches = re.findall(pattern, query, re.IGNORECASE)
            columns.extend(matches)
        
        if columns:
            params["columns"] = list(dict.fromkeys(columns))  # Remove duplicates, preserve order
        
        # Extract update values - look for "to 'X'" or "= 'X'" patterns
        if params.get("sql_keyword") == "UPDATE":
            update_patterns = [
                r"to\s+['\"]([^'\"]+)['\"]",
                r"=\s*['\"]([^'\"]+)['\"]",
                r"set\s+\w+\s+to\s+['\"]?(\w+)['\"]?",
            ]
            update_values = []
            for pattern in update_patterns:
                matches = re.findall(pattern, query, re.IGNORECASE)
                update_values.extend(matches)
            
            if update_values:
                params["update_values"] = list(dict.fromkeys(update_values))
        
        # Extract conditions - look for "where X > Y" or "whose X is greater than Y" patterns
        condition_patterns = [
            # "whose Age is greater than 18" -> "Age > 18"
            (r'whose\s+["\']?(\w+)["\']?\s+is\s+greater\s+than\s+(\d+)', '{} > {}'),
            (r'whose\s+["\']?(\w+)["\']?\s+is\s+less\s+than\s+(\d+)', '{} < {}'),
            (r'whose\s+["\']?(\w+)["\']?\s+(?:is|=|equals?)\s+["\']?([^"\']+)["\']?', '{} = {}'),
            # "where Age > 18"
            (r'where\s+["\']?(\w+)["\']?\s*>\s*(\d+)', '{} > {}'),
            (r'where\s+["\']?(\w+)["\']?\s*<\s*(\d+)', '{} < {}'),
            (r'where\s+["\']?(\w+)["\']?\s*=\s*["\']?([^"\']+)["\']?', '{} = {}'),
            # "if Age > 18"
            (r'if\s+["\']?(\w+)["\']?\s+is\s+greater\s+than\s+(\d+)', '{} > {}'),
            (r'if\s+["\']?(\w+)["\']?\s+is\s+less\s+than\s+(\d+)', '{} < {}'),
        ]
        
        conditions = []
        for pattern, fmt in condition_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                cond = fmt.format(match.group(1), match.group(2))
                conditions.append(cond)
                break
        
        if conditions:
            params["conditions"] = [conditions]
    
    return {func_name: params}
