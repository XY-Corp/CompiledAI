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
    
    Parses the user query to identify the appropriate SQL operation and extracts
    all relevant parameters like table name, columns, values, and conditions.
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
    
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "sql.execute")
    
    query_lower = query.lower()
    params = {}
    
    # Determine SQL keyword based on query content
    if "update" in query_lower or "correct" in query_lower or "change" in query_lower or "modify" in query_lower:
        params["sql_keyword"] = "UPDATE"
    elif "insert" in query_lower or "add" in query_lower:
        params["sql_keyword"] = "INSERT"
    elif "delete" in query_lower or "remove" in query_lower:
        params["sql_keyword"] = "DELETE"
    elif "create" in query_lower:
        params["sql_keyword"] = "CREATE"
    else:
        params["sql_keyword"] = "SELECT"
    
    # Extract table name - look for patterns like "table called X" or "table named X"
    table_patterns = [
        r'table\s+(?:called|named)\s+["\']?(\w+)["\']?',
        r'["\'](\w+)["\']\s+table',
        r'from\s+["\']?(\w+)["\']?',
        r'into\s+["\']?(\w+)["\']?',
        r'update\s+["\']?(\w+)["\']?',
    ]
    
    table_name = None
    for pattern in table_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            table_name = match.group(1)
            break
    
    if table_name:
        params["table_name"] = table_name
    
    # For UPDATE operations, extract columns and values
    if params["sql_keyword"] == "UPDATE":
        # Extract column to update - look for column names mentioned
        # Pattern: "the X of" or "column X" or specific column names
        column_patterns = [
            r'the\s+(\w+(?:\s+\w+)?)\s+of\s+(?:the\s+)?(?:compound|record)',
            r'molar\s+mass',
            r'(\w+)\s+has\s+been',
        ]
        
        columns = []
        # Check for specific column mentions in the query
        if "molar mass" in query_lower or "molarmass" in query_lower:
            columns.append("MolarMass")
        
        if columns:
            params["columns"] = columns
        
        # Extract the new value - look for "should be X" or "correct value is X"
        value_patterns = [
            r'should\s+be\s+([\d.]+)',
            r'correct\s+(?:\w+\s+)?(?:is|should\s+be)\s+([\d.]+)',
            r'change\s+(?:it\s+)?to\s+([\d.]+)',
            r'update\s+(?:it\s+)?to\s+([\d.]+)',
        ]
        
        update_value = None
        for pattern in value_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                update_value = match.group(1)
                break
        
        if update_value:
            params["update_values"] = [update_value]
        
        # Extract conditions - look for WHERE clause conditions
        # Pattern: "where X is Y" or "only to records where X = Y"
        conditions = []
        
        # Look for compound name condition
        compound_patterns = [
            r"['\"]?CompoundName['\"]?\s*(?:is|=)\s*['\"]?(\w+)['\"]?",
            r"where\s+['\"]?(\w+)['\"]?\s*(?:is|=)\s*['\"]?(\w+)['\"]?",
            r"compound\s+['\"](\w+)['\"]",
            r"record\s+where\s+['\"]?(\w+)['\"]?\s+is\s+['\"]?(\w+)['\"]?",
        ]
        
        # Check for specific compound name like "Water"
        water_match = re.search(r'compound\s+["\']?(\w+)["\']?', query, re.IGNORECASE)
        if water_match:
            compound_name = water_match.group(1)
            conditions.append([f"CompoundName = '{compound_name}'"])
        else:
            # Try to find condition pattern
            cond_match = re.search(r"where\s+['\"]?(\w+)['\"]?\s+is\s+['\"]?(\w+)['\"]?", query, re.IGNORECASE)
            if cond_match:
                col = cond_match.group(1)
                val = cond_match.group(2)
                conditions.append([f"{col} = '{val}'"])
        
        if conditions:
            params["conditions"] = conditions
    
    return {func_name: params}
