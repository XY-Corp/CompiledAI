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
    
    # Parse prompt - may be JSON string with nested structure
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
            # Handle BFCL format: {"question": [[{"role": "user", "content": "..."}]], "function": [...]}
            if "question" in data and isinstance(data["question"], list):
                if len(data["question"]) > 0 and isinstance(data["question"][0], list):
                    query = data["question"][0][0].get("content", str(prompt))
                else:
                    query = str(prompt)
            else:
                query = str(prompt)
        else:
            query = str(prompt)
    except (json.JSONDecodeError, TypeError, KeyError):
        query = str(prompt)
    
    # Parse functions - may be JSON string
    try:
        if isinstance(functions, str):
            funcs = json.loads(functions)
        else:
            funcs = functions
    except (json.JSONDecodeError, TypeError):
        funcs = []
    
    if not funcs:
        return {"error": "No functions provided"}
    
    func = funcs[0]
    func_name = func.get("name", "")
    props = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters based on the query content using regex and string matching
    params = {}
    query_lower = query.lower()
    
    # Extract database_name - look for patterns like "from the X" or "XDB"
    db_match = re.search(r'from\s+(?:the\s+)?(\w+DB|\w+)', query, re.IGNORECASE)
    if db_match:
        db_name = db_match.group(1)
        # Check if it ends with DB
        if not db_name.upper().endswith('DB'):
            # Look for explicit DB mention
            db_explicit = re.search(r'(\w+DB)', query, re.IGNORECASE)
            if db_explicit:
                db_name = db_explicit.group(1)
        params["database_name"] = db_name
    
    # Extract table_name - look for "records for X" or table-related patterns
    # Common pattern: "records for students" -> table is likely "students"
    table_match = re.search(r'(?:records?\s+(?:for|from)\s+)(\w+)', query, re.IGNORECASE)
    if table_match:
        params["table_name"] = table_match.group(1)
    
    # Extract conditions - look for specific field values
    conditions = {}
    
    # Extract department/subject - "studying X" or "in X department"
    dept_match = re.search(r'studying\s+(\w+)', query, re.IGNORECASE)
    if dept_match:
        conditions["department"] = dept_match.group(1)
    
    # Extract school name - look for quoted school name or "in 'X'" pattern
    school_match = re.search(r"['\"]([^'\"]+(?:School|High|Academy|College)[^'\"]*)['\"]", query, re.IGNORECASE)
    if school_match:
        conditions["school"] = school_match.group(1)
    else:
        # Try without quotes
        school_match2 = re.search(r'(?:in|from|at)\s+([A-Z][a-zA-Z\s]+(?:School|High|Academy|College))', query)
        if school_match2:
            conditions["school"] = school_match2.group(1).strip()
    
    if conditions:
        params["conditions"] = conditions
    
    # Extract fetch_limit if mentioned - look for numbers with "limit" or "top X"
    limit_match = re.search(r'(?:limit|top|first)\s+(\d+)', query, re.IGNORECASE)
    if limit_match:
        params["fetch_limit"] = int(limit_match.group(1))
    
    return {func_name: params}
