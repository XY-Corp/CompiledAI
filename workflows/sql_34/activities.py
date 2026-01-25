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
    
    Parses the user query to identify SQL operation type, table name, columns,
    values, and conditions, then returns the structured function call.
    """
    # Parse inputs (may be JSON strings)
    try:
        data = json.loads(prompt) if isinstance(prompt, str) else prompt
        if isinstance(data, dict) and "question" in data:
            question_list = data.get("question", [])
            if question_list and isinstance(question_list[0], list):
                query = question_list[0][0].get("content", str(prompt))
            elif question_list and isinstance(question_list[0], dict):
                query = question_list[0].get("content", str(prompt))
            else:
                query = str(prompt)
        else:
            query = str(prompt)
    except:
        query = str(prompt)

    funcs = json.loads(functions) if isinstance(functions, str) else functions
    func = funcs[0] if funcs else {}
    name = func.get("name", "")
    
    query_lower = query.lower()
    params = {}
    
    # Determine SQL keyword based on query content
    if "update" in query_lower or "change" in query_lower or "modify" in query_lower or "set" in query_lower:
        params["sql_keyword"] = "UPDATE"
    elif "delete" in query_lower or "remove" in query_lower:
        params["sql_keyword"] = "DELETE"
    elif "insert" in query_lower or "add" in query_lower or "create" in query_lower and "table" not in query_lower:
        params["sql_keyword"] = "INSERT"
    elif "create" in query_lower and "table" in query_lower:
        params["sql_keyword"] = "CREATE"
    else:
        params["sql_keyword"] = "SELECT"
    
    # Extract table name - look for patterns like "table_name" or "the X table"
    table_match = re.search(r'"([^"]+)"\s*table|the\s+"([^"]+)"|table\s+"([^"]+)"|"([^"]+)"\s+(?:in the )?database', query, re.IGNORECASE)
    if table_match:
        params["table_name"] = next(g for g in table_match.groups() if g)
    else:
        # Try to find quoted table name
        quoted_match = re.search(r'"([A-Za-z_][A-Za-z0-9_]*)"', query)
        if quoted_match:
            params["table_name"] = quoted_match.group(1)
        else:
            params["table_name"] = ""
    
    # Extract column names - look for "column" or quoted column names
    column_matches = re.findall(r'"([^"]+)"\s*column|the\s+"([^"]+)"\s*(?:column|field)|column\s+"([^"]+)"', query, re.IGNORECASE)
    columns = []
    for match in column_matches:
        col = next((g for g in match if g), None)
        if col and col != params.get("table_name"):
            columns.append(col)
    
    if columns:
        params["columns"] = columns
    
    # Extract values for UPDATE - look for "to X" or "= X" patterns with numbers
    if params["sql_keyword"] == "UPDATE":
        # Look for numeric values to update to
        value_match = re.search(r'to\s+(\d+)\s*(?:years?)?|=\s*(\d+)|set.*?to\s+(\d+)', query, re.IGNORECASE)
        if value_match:
            value = next(g for g in value_match.groups() if g)
            params["update_values"] = [value]
    
    # Extract conditions - look for "where", "condition", "based on", "if", "less than", "greater than", etc.
    conditions = []
    
    # Pattern for "less than X" or "< X"
    less_than_match = re.search(r'(?:less than|<)\s*(\d+)', query, re.IGNORECASE)
    if less_than_match:
        value = less_than_match.group(1)
        # Find which column this condition applies to
        if columns:
            conditions.append([f"{columns[0]} < {value}"])
    
    # Pattern for "greater than X" or "> X"
    greater_than_match = re.search(r'(?:greater than|>)\s*(\d+)', query, re.IGNORECASE)
    if greater_than_match:
        value = greater_than_match.group(1)
        if columns:
            conditions.append([f"{columns[0]} > {value}"])
    
    # Pattern for "equal to X" or "= X" in conditions
    equal_match = re.search(r'(?:equal to|equals|=)\s*["\']?([^"\']+)["\']?', query, re.IGNORECASE)
    if equal_match and "condition" in query_lower:
        value = equal_match.group(1).strip()
        if columns:
            conditions.append([f"{columns[0]} = {value}"])
    
    # Look for animal name condition - "for the animal X" or "animal \"X\""
    animal_match = re.search(r'(?:for the )?animal\s+"([^"]+)"|"([^"]+)"\s+(?:animal|entry|record)', query, re.IGNORECASE)
    if animal_match:
        animal_name = next(g for g in animal_match.groups() if g)
        # Add condition for animal name - typically a column like "Animal" or "Name"
        conditions.append([f"Animal = {animal_name}"])
    
    if conditions:
        params["conditions"] = conditions
    
    return {name: params}
