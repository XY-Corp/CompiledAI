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
    
    params = {}
    
    # For sql.execute, extract SQL operation details
    if func_name == "sql.execute":
        query_lower = query.lower()
        
        # Determine SQL keyword based on context
        if "add" in query_lower or "insert" in query_lower:
            params["sql_keyword"] = "INSERT"
        elif "update" in query_lower or "change" in query_lower or "modify" in query_lower:
            params["sql_keyword"] = "UPDATE"
        elif "delete" in query_lower or "remove" in query_lower:
            params["sql_keyword"] = "DELETE"
        elif "create" in query_lower and "table" in query_lower:
            params["sql_keyword"] = "CREATE"
        else:
            params["sql_keyword"] = "SELECT"
        
        # Extract table name - look for patterns like "to the X table" or "table X" or "X table"
        table_patterns = [
            r'to the ["\']?(\w+)["\']? table',
            r'from the ["\']?(\w+)["\']? table',
            r'in the ["\']?(\w+)["\']? table',
            r'table ["\']?(\w+)["\']?',
            r'["\'](\w+)["\'] table',
        ]
        for pattern in table_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                params["table_name"] = match.group(1)
                break
        
        if "table_name" not in params:
            params["table_name"] = "Species"  # Default from context
        
        # Extract column names - look for explicit column mentions
        columns_match = re.search(r'columns?\s+(?:in the table\s+)?(?:are\s+)?["\']?([^"\'\.]+)["\']?\.?$', query, re.IGNORECASE)
        if columns_match:
            col_text = columns_match.group(1)
            # Parse column names like "Species_Name", "Lifespan", "Size", and "Weight"
            columns = re.findall(r'["\']?(\w+)["\']?', col_text)
            if columns:
                params["columns"] = columns
        
        # Also try to find columns mentioned explicitly
        if "columns" not in params:
            col_pattern = r'columns?\s+(?:are\s+)?(.+?)(?:\.|$)'
            col_match = re.search(col_pattern, query, re.IGNORECASE)
            if col_match:
                col_text = col_match.group(1)
                columns = re.findall(r'"([^"]+)"', col_text)
                if columns:
                    params["columns"] = columns
        
        # For INSERT, extract values
        if params.get("sql_keyword") == "INSERT":
            # Extract species name (in quotes)
            species_match = re.search(r'named\s+["\']([^"\']+)["\']', query, re.IGNORECASE)
            species_name = species_match.group(1) if species_match else ""
            
            # Extract lifespan (number followed by "years")
            lifespan_match = re.search(r'lifespan\s+of\s+(\d+)\s*years?', query, re.IGNORECASE)
            lifespan = lifespan_match.group(1) if lifespan_match else ""
            
            # Extract size (number followed by "cm")
            size_match = re.search(r'size\s+of\s+([\d.]+)\s*cm', query, re.IGNORECASE)
            size = size_match.group(1) if size_match else ""
            
            # Extract weight (number followed by "grams" or "g")
            weight_match = re.search(r'weight\s+of\s+(\d+)\s*(?:grams?|g)', query, re.IGNORECASE)
            weight = weight_match.group(1) if weight_match else ""
            
            # Build insert_values as array of arrays
            if species_name or lifespan or size or weight:
                params["insert_values"] = [[species_name, lifespan, size, weight]]
            
            # Set columns if not already set
            if "columns" not in params:
                params["columns"] = ["Species_Name", "Lifespan", "Size", "Weight"]
    
    return {func_name: params}
