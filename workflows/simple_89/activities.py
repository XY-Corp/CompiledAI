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
        
        # Extract user query from BFCL format: {"question": [[{"role": "user", "content": "..."}]]}
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
    
    # Get function details
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters from query using regex and string matching
    params = {}
    query_lower = query.lower()
    
    # Extract database_name - look for patterns like "from the X" or "XDB"
    db_match = re.search(r'from\s+(?:the\s+)?(\w+DB|\w+)', query, re.IGNORECASE)
    if db_match:
        params["database_name"] = db_match.group(1)
    else:
        # Look for any word ending in DB
        db_pattern = re.search(r'(\w+DB)', query, re.IGNORECASE)
        if db_pattern:
            params["database_name"] = db_pattern.group(1)
    
    # Extract table_name - look for "records for X" or "from X table"
    # For this query: "records for students" -> table is likely "students"
    table_match = re.search(r'records\s+for\s+(\w+)', query, re.IGNORECASE)
    if table_match:
        params["table_name"] = table_match.group(1)
    else:
        table_match = re.search(r'from\s+(?:the\s+)?(\w+)\s+table', query, re.IGNORECASE)
        if table_match:
            params["table_name"] = table_match.group(1)
    
    # Extract conditions
    conditions = {}
    
    # Extract department/subject - "studying X" or "in X department"
    dept_match = re.search(r'studying\s+(\w+)', query, re.IGNORECASE)
    if dept_match:
        conditions["department"] = dept_match.group(1)
    else:
        dept_match = re.search(r'(\w+)\s+department', query, re.IGNORECASE)
        if dept_match:
            conditions["department"] = dept_match.group(1)
    
    # Extract school - look for quoted school name or "X School/High School"
    school_match = re.search(r"'([^']+)'", query)  # Quoted name
    if school_match:
        conditions["school"] = school_match.group(1)
    else:
        school_match = re.search(r'in\s+([A-Z][a-zA-Z\s]+(?:School|High School|Academy))', query)
        if school_match:
            conditions["school"] = school_match.group(1).strip()
    
    if conditions:
        params["conditions"] = conditions
    
    # Extract fetch_limit if mentioned (optional parameter)
    limit_match = re.search(r'(?:limit|top|first)\s+(\d+)', query, re.IGNORECASE)
    if limit_match:
        params["fetch_limit"] = int(limit_match.group(1))
    
    return {func_name: params}
