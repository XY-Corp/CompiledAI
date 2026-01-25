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
    function name and parameters. Returns format: {"function_name": {params}}.
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
    
    # For database.query, extract table name and conditions
    params = {}
    
    # Extract table name - look for "in X table" or "from X table" patterns
    table_match = re.search(r'(?:in|from)\s+(?:database\s+in\s+)?(\w+)\s+table', query, re.IGNORECASE)
    if table_match:
        params["table"] = table_match.group(1)
    
    # Extract conditions from the query
    conditions = []
    
    # Pattern for "field is/= 'value'" or "field = value"
    eq_patterns = [
        r"(\w+)\s+is\s+'([^']+)'",  # field is 'value'
        r"(\w+)\s+is\s+\"([^\"]+)\"",  # field is "value"
        r"(\w+)\s+=\s+'([^']+)'",  # field = 'value'
        r"(\w+)\s+=\s+\"([^\"]+)\"",  # field = "value"
    ]
    
    for pattern in eq_patterns:
        matches = re.findall(pattern, query, re.IGNORECASE)
        for match in matches:
            field, value = match
            conditions.append({
                "field": field,
                "operation": "=",
                "value": value
            })
    
    # Pattern for "field > number" or "field is greater than number"
    gt_patterns = [
        r"(\w+)\s+is\s+greater\s+than\s+(\d+)",  # field is greater than N
        r"(\w+)\s+>\s+(\d+)",  # field > N
    ]
    
    for pattern in gt_patterns:
        matches = re.findall(pattern, query, re.IGNORECASE)
        for match in matches:
            field, value = match
            conditions.append({
                "field": field,
                "operation": ">",
                "value": value
            })
    
    # Pattern for "field < number" or "field is less than number"
    lt_patterns = [
        r"(\w+)\s+is\s+less\s+than\s+(\d+)",  # field is less than N
        r"(\w+)\s+<\s+(\d+)",  # field < N
    ]
    
    for pattern in lt_patterns:
        matches = re.findall(pattern, query, re.IGNORECASE)
        for match in matches:
            field, value = match
            conditions.append({
                "field": field,
                "operation": "<",
                "value": value
            })
    
    # Pattern for ">=" or "greater than or equal"
    gte_patterns = [
        r"(\w+)\s+is\s+greater\s+than\s+or\s+equal\s+to\s+(\d+)",
        r"(\w+)\s+>=\s+(\d+)",
    ]
    
    for pattern in gte_patterns:
        matches = re.findall(pattern, query, re.IGNORECASE)
        for match in matches:
            field, value = match
            conditions.append({
                "field": field,
                "operation": ">=",
                "value": value
            })
    
    # Pattern for "<=" or "less than or equal"
    lte_patterns = [
        r"(\w+)\s+is\s+less\s+than\s+or\s+equal\s+to\s+(\d+)",
        r"(\w+)\s+<=\s+(\d+)",
    ]
    
    for pattern in lte_patterns:
        matches = re.findall(pattern, query, re.IGNORECASE)
        for match in matches:
            field, value = match
            conditions.append({
                "field": field,
                "operation": "<=",
                "value": value
            })
    
    if conditions:
        params["conditions"] = conditions
    
    return {func_name: params}
