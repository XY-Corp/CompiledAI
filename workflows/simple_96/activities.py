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
    function name and parameters using regex and string matching.
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
    
    # For database.query, extract table and conditions
    params = {}
    
    # Extract table name - look for "in X table" or "from X table" patterns
    table_patterns = [
        r'in\s+(\w+)\s+table',
        r'from\s+(\w+)\s+table',
        r'table\s+(\w+)',
        r'in\s+database\s+in\s+(\w+)\s+table',
    ]
    
    table_name = None
    for pattern in table_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            table_name = match.group(1)
            break
    
    if table_name:
        params["table"] = table_name
    
    # Extract conditions - look for field, operation, value patterns
    conditions = []
    
    # Pattern for conditions like "age is greater than 25" or "field > value"
    condition_patterns = [
        # "field is greater than value" / "field is less than value"
        (r'(\w+)\s+is\s+greater\s+than\s+(\d+)', '>'),
        (r'(\w+)\s+is\s+less\s+than\s+(\d+)', '<'),
        (r'(\w+)\s+is\s+greater\s+than\s+or\s+equal\s+to\s+(\d+)', '>='),
        (r'(\w+)\s+is\s+less\s+than\s+or\s+equal\s+to\s+(\d+)', '<='),
        (r'(\w+)\s+is\s+equal\s+to\s+(\d+)', '='),
        # "field > value" style
        (r'(\w+)\s*>\s*(\d+)', '>'),
        (r'(\w+)\s*<\s*(\d+)', '<'),
        (r'(\w+)\s*>=\s*(\d+)', '>='),
        (r'(\w+)\s*<=\s*(\d+)', '<='),
        (r'(\w+)\s*=\s*(\d+)', '='),
    ]
    
    # Extract numeric conditions
    for pattern, operation in condition_patterns:
        for match in re.finditer(pattern, query, re.IGNORECASE):
            field = match.group(1)
            value = match.group(2)
            # Avoid duplicates
            if not any(c["field"] == field and c["operation"] == operation for c in conditions):
                conditions.append({
                    "field": field,
                    "operation": operation,
                    "value": value
                })
    
    # Extract string equality conditions like "job is 'engineer'" or "field = 'value'"
    string_patterns = [
        r"(\w+)\s+is\s+['\"]([^'\"]+)['\"]",
        r"(\w+)\s*=\s*['\"]([^'\"]+)['\"]",
    ]
    
    for pattern in string_patterns:
        for match in re.finditer(pattern, query, re.IGNORECASE):
            field = match.group(1)
            value = match.group(2)
            # Skip if field is a common word that's not a field name
            if field.lower() in ['is', 'and', 'or', 'where', 'the']:
                continue
            # Avoid duplicates
            if not any(c["field"] == field and c["value"] == value for c in conditions):
                conditions.append({
                    "field": field,
                    "operation": "=",
                    "value": value
                })
    
    if conditions:
        params["conditions"] = conditions
    
    return {func_name: params}
