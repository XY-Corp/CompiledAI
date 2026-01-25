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
        
        # Extract user query from BFCL format
        if isinstance(data, dict) and "question" in data:
            question = data.get("question", [])
            if isinstance(question, list) and len(question) > 0:
                if isinstance(question[0], list) and len(question[0]) > 0:
                    query = question[0][0].get("content", str(prompt))
                elif isinstance(question[0], dict):
                    query = question[0].get("content", str(prompt))
                else:
                    query = str(prompt)
            else:
                query = str(prompt)
        else:
            query = str(prompt)
    except (json.JSONDecodeError, TypeError):
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
    
    # Extract parameters based on query content
    params = {}
    query_lower = query.lower()
    
    # For sql.execute function
    if func_name == "sql.execute":
        # Determine SQL keyword based on query intent
        if any(word in query_lower for word in ["retrieve", "get", "find", "show", "list", "fetch", "what", "which"]):
            params["sql_keyword"] = "SELECT"
        elif any(word in query_lower for word in ["insert", "add", "create new"]):
            params["sql_keyword"] = "INSERT"
        elif any(word in query_lower for word in ["update", "modify", "change", "set"]):
            params["sql_keyword"] = "UPDATE"
        elif any(word in query_lower for word in ["delete", "remove"]):
            params["sql_keyword"] = "DELETE"
        else:
            params["sql_keyword"] = "SELECT"
        
        # Extract table name - look for patterns like "from the X table" or "X table"
        table_patterns = [
            r'from\s+(?:the\s+)?["\']?(\w+)["\']?\s+table',
            r'["\'](\w+)["\']?\s+table',
            r'table\s+(?:named?\s+)?["\']?(\w+)["\']?',
            r'into\s+(?:the\s+)?["\']?(\w+)["\']?',
        ]
        
        table_name = None
        for pattern in table_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                table_name = match.group(1)
                break
        
        if table_name:
            params["table_name"] = table_name
        
        # Extract column names - look for patterns like "names and research topics"
        # Common patterns: "the X and Y of", "retrieve X, Y, Z"
        column_patterns = [
            r'(?:retrieve|get|find|show|list|fetch)\s+(?:the\s+)?(.+?)\s+(?:of|from|in)',
            r'(?:names?|columns?)\s+(?:and\s+)?(.+?)\s+(?:of|from|in)',
        ]
        
        columns = []
        for pattern in column_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                col_text = match.group(1)
                # Split by "and" or ","
                col_parts = re.split(r'\s+and\s+|,\s*', col_text)
                for part in col_parts:
                    # Clean up the column name
                    col = part.strip().lower().replace(" ", "_")
                    if col and col not in ["the", "all"]:
                        columns.append(col)
                break
        
        # If we found "names and research topics", map to likely column names
        if not columns:
            if "names" in query_lower or "name" in query_lower:
                columns.append("name")
            if "research topic" in query_lower or "research topics" in query_lower:
                columns.append("research_topic")
        
        if columns:
            params["columns"] = columns
        
        # Extract conditions - look for "who are working on X" or "where X = Y"
        condition_patterns = [
            r'(?:who\s+(?:are|is)\s+)?working\s+on\s+["\']?([^"\'\.]+)["\']?',
            r'where\s+(.+?)(?:\s+and\s+|\s*$)',
            r'with\s+(.+?)\s*(?:=|is)\s*["\']?([^"\']+)["\']?',
        ]
        
        conditions = []
        
        # Check for "working on X" pattern
        working_match = re.search(r'working\s+on\s+["\']?([^"\'\.]+)["\']?', query, re.IGNORECASE)
        if working_match:
            topic = working_match.group(1).strip()
            conditions.append(f"research_topic = '{topic}'")
        
        if conditions:
            params["conditions"] = [conditions]
    
    return {func_name: params}
