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
            if "question" in data and isinstance(data["question"], list):
                query = data["question"][0][0].get("content", prompt) if data["question"] and data["question"][0] else prompt
            else:
                query = str(prompt)
        else:
            query = str(prompt)
    except (json.JSONDecodeError, TypeError, IndexError, KeyError):
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
    
    params = {}
    query_lower = query.lower()
    
    # Extract sql_keyword based on action words in query
    if "sql_keyword" in props:
        if any(word in query_lower for word in ["erase", "delete", "remove"]):
            params["sql_keyword"] = "DELETE"
        elif any(word in query_lower for word in ["insert", "add", "create record"]):
            params["sql_keyword"] = "INSERT"
        elif any(word in query_lower for word in ["update", "modify", "change", "set"]):
            params["sql_keyword"] = "UPDATE"
        elif any(word in query_lower for word in ["select", "fetch", "get", "retrieve", "find"]):
            params["sql_keyword"] = "SELECT"
        elif any(word in query_lower for word in ["create table", "create database"]):
            params["sql_keyword"] = "CREATE"
    
    # Extract table_name - look for patterns like "table named X" or "table X"
    if "table_name" in props:
        table_patterns = [
            r'table\s+named\s+["\']?(\w+)["\']?',
            r'table\s+["\']?(\w+)["\']?',
            r'from\s+["\']?(\w+)["\']?',
            r'into\s+["\']?(\w+)["\']?',
        ]
        for pattern in table_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                params["table_name"] = match.group(1)
                break
    
    # Extract columns - look for quoted column names or patterns like "columns X, Y, Z"
    if "columns" in props:
        # Look for explicit column mentions
        columns_match = re.search(r'columns?\s+(?:involved\s+)?(?:in\s+this\s+operation\s+)?(?:are\s+)?["\']?([^.]+?)["\']?(?:\.|$)', query, re.IGNORECASE)
        if columns_match:
            col_text = columns_match.group(1)
            # Extract quoted column names
            quoted_cols = re.findall(r'["\'](\w+)["\']', col_text)
            if quoted_cols:
                params["columns"] = quoted_cols
            else:
                # Try comma-separated words
                cols = re.findall(r'\b([A-Z][a-zA-Z]+)\b', col_text)
                if cols:
                    params["columns"] = cols
    
    # Extract conditions - look for comparison patterns
    if "conditions" in props:
        conditions = []
        # Pattern: "scored less than X" -> "FinalScore < X"
        less_than_match = re.search(r'scored?\s+less\s+than\s+(\d+)', query, re.IGNORECASE)
        if less_than_match:
            value = less_than_match.group(1)
            # Find the score column name
            score_col = "FinalScore"  # default
            if "columns" in params:
                for col in params["columns"]:
                    if "score" in col.lower():
                        score_col = col
                        break
            conditions.append([f"{score_col} < {value}"])
        
        # Pattern: "greater than X"
        greater_than_match = re.search(r'(?:scored?\s+)?(?:greater|more)\s+than\s+(\d+)', query, re.IGNORECASE)
        if greater_than_match and not less_than_match:
            value = greater_than_match.group(1)
            score_col = "FinalScore"
            if "columns" in params:
                for col in params["columns"]:
                    if "score" in col.lower():
                        score_col = col
                        break
            conditions.append([f"{score_col} > {value}"])
        
        # Pattern: "equal to X" or "equals X"
        equals_match = re.search(r'(?:equal(?:s)?\s+(?:to\s+)?|=\s*)(\d+)', query, re.IGNORECASE)
        if equals_match and not less_than_match and not greater_than_match:
            value = equals_match.group(1)
            conditions.append([f"value = {value}"])
        
        if conditions:
            params["conditions"] = conditions
    
    return {func_name: params}
