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
    
    # Initialize params dict
    params = {}
    query_lower = query.lower()
    
    # Extract SQL-specific parameters
    if "sql" in func_name.lower():
        # Extract SQL keyword
        if "sql_keyword" in props:
            # Determine operation type from query
            if any(word in query_lower for word in ["what are", "names of", "list", "show", "get", "find", "retrieve"]):
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
        
        # Extract table name - look for patterns like "in the X table" or "from X table"
        if "table_name" in props:
            table_patterns = [
                r'(?:in|from|into|update)\s+(?:the\s+)?["\']?(\w+)["\']?\s+table',
                r'table\s+(?:named?\s+)?["\']?(\w+)["\']?',
                r'["\'](\w+)["\']?\s+table',
            ]
            for pattern in table_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    params["table_name"] = match.group(1)
                    break
        
        # Extract columns - look for column names in quotes or after "columns"
        if "columns" in props:
            # Look for quoted column names
            quoted_cols = re.findall(r'["\'](\w+)["\']', query)
            
            # Filter to likely column names (exclude table names and keywords)
            table_name = params.get("table_name", "").lower()
            sql_keywords = {"select", "from", "where", "and", "or", "in", "the", "table", "database"}
            
            columns = []
            for col in quoted_cols:
                col_lower = col.lower()
                if col_lower != table_name and col_lower not in sql_keywords:
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
        
        # Extract conditions - look for comparison patterns
        if "conditions" in props:
            conditions = []
            
            # Pattern for conditions like "lifespan greater than 50" or "age > 30"
            condition_patterns = [
                # "X greater than Y" or "X is greater than Y"
                (r'(\w+)\s+(?:is\s+)?greater\s+than\s+(\d+)', '>', None),
                # "X less than Y" or "X is less than Y"
                (r'(\w+)\s+(?:is\s+)?less\s+than\s+(\d+)', '<', None),
                # "X equal to Y" or "X equals Y"
                (r'(\w+)\s+(?:is\s+)?equal(?:s)?\s+(?:to\s+)?(\d+)', '=', None),
                # "X >= Y" or "X > Y" etc
                (r'(\w+)\s*(>=|<=|>|<|=)\s*(\d+)', None, None),
            ]
            
            for pattern, operator, _ in condition_patterns:
                matches = re.finditer(pattern, query, re.IGNORECASE)
                for match in matches:
                    groups = match.groups()
                    if operator:
                        # Pattern with word-based operator
                        col_name = groups[0]
                        value = groups[1]
                        conditions.append(f"{col_name} {operator} {value}")
                    else:
                        # Pattern with symbol operator
                        col_name = groups[0]
                        op = groups[1]
                        value = groups[2]
                        conditions.append(f"{col_name} {op} {value}")
            
            if conditions:
                # Return as nested array format per schema
                params["conditions"] = [conditions]
    
    return {func_name: params}
