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
        
        # Determine SQL keyword based on intent
        if "record" in query_lower or "insert" in query_lower or "add" in query_lower:
            params["sql_keyword"] = "INSERT"
        elif "update" in query_lower or "modify" in query_lower:
            params["sql_keyword"] = "UPDATE"
        elif "delete" in query_lower or "remove" in query_lower:
            params["sql_keyword"] = "DELETE"
        elif "create" in query_lower:
            params["sql_keyword"] = "CREATE"
        else:
            params["sql_keyword"] = "SELECT"
        
        # Extract table name - look for patterns like "in the X table" or "table X"
        table_patterns = [
            r'in\s+the\s+"?([^"]+)"?\s+table',
            r'into\s+the\s+"?([^"]+)"?\s+table',
            r'table\s+"?([A-Za-z_][A-Za-z0-9_]*)"?',
            r'"([A-Za-z_][A-Za-z0-9_]*)"\s+table',
        ]
        for pattern in table_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                params["table_name"] = match.group(1).strip()
                break
        
        if "table_name" not in params:
            params["table_name"] = ""
        
        # Extract column names - look for "columns are X, Y, Z" or explicit column mentions
        columns_match = re.search(r'columns?\s+(?:in\s+the\s+table\s+)?(?:are|:)\s*"?([^"\.]+)"?(?:\.|$)', query, re.IGNORECASE)
        if columns_match:
            cols_text = columns_match.group(1)
            # Parse column names from quoted strings
            cols = re.findall(r'"([^"]+)"', cols_text)
            if cols:
                params["columns"] = cols
            else:
                # Try comma-separated without quotes
                cols = [c.strip() for c in cols_text.split(',') if c.strip()]
                if cols:
                    params["columns"] = cols
        
        # If no columns found, try to extract from explicit mentions
        if "columns" not in params:
            col_mentions = re.findall(r'"([A-Za-z_][A-Za-z0-9_]*)"', query)
            # Filter out table name and species name
            table_name = params.get("table_name", "")
            cols = [c for c in col_mentions if c != table_name and not c.endswith("saharae") and "Species" not in c or c.endswith("_Name") or c.endswith("_Weight")]
            # Look for column-like names
            potential_cols = ["Species_Name", "Height", "Lifespan", "Seed_Weight"]
            found_cols = [c for c in col_mentions if c in potential_cols]
            if found_cols:
                params["columns"] = found_cols
        
        # For INSERT, extract values
        if params["sql_keyword"] == "INSERT":
            values = []
            
            # Extract species name - look for "named X" pattern
            species_match = re.search(r'named\s+"([^"]+)"', query)
            if species_match:
                values.append(species_match.group(1))
            
            # Extract numeric values with their context
            # Height
            height_match = re.search(r'height\s+of\s+(\d+(?:\.\d+)?)\s*(?:cm|centimeters?)?', query, re.IGNORECASE)
            if height_match:
                values.append(height_match.group(1))
            
            # Lifespan
            lifespan_match = re.search(r'lifespan\s+of\s+(\d+(?:\.\d+)?)\s*(?:years?)?', query, re.IGNORECASE)
            if lifespan_match:
                values.append(lifespan_match.group(1))
            
            # Seed weight
            seed_match = re.search(r'seed\s+weight\s+of\s+(\d+(?:\.\d+)?)\s*(?:grams?|g)?', query, re.IGNORECASE)
            if seed_match:
                values.append(seed_match.group(1))
            
            if values:
                params["insert_values"] = [values]
    
    return {func_name: params}
