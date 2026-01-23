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
    """Extract function call from user query and return as {func_name: {params}}.
    
    Parses the prompt to extract the user's query, identifies the target function,
    and extracts parameter values using regex and string matching.
    """
    # Parse prompt (may be JSON string with nested structure)
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
        else:
            data = prompt
        
        # Extract user query from BFCL format: {"question": [[{"role": "user", "content": "..."}]]}
        if "question" in data and isinstance(data["question"], list):
            if len(data["question"]) > 0 and isinstance(data["question"][0], list):
                if len(data["question"][0]) > 0 and isinstance(data["question"][0][0], dict):
                    query = data["question"][0][0].get("content", str(prompt))
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
    
    # Get target function details
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters based on schema
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        
        if param_type == "array":
            items_type = param_info.get("items", {}).get("type", "string")
            
            if items_type == "string":
                # For company names, stock symbols, etc. - extract proper nouns/entities
                # Common patterns: "X and Y", "X, Y, and Z", etc.
                
                # Look for company names (capitalized words or known patterns)
                # Pattern 1: Extract words after "of" that are capitalized
                company_pattern = r'\b(?:of|for)\s+([A-Z][a-zA-Z]+(?:\s+and\s+[A-Z][a-zA-Z]+)*)'
                match = re.search(company_pattern, query)
                
                if match:
                    # Split by "and" or ","
                    companies_str = match.group(1)
                    companies = re.split(r'\s+and\s+|\s*,\s*', companies_str)
                    params[param_name] = [c.strip() for c in companies if c.strip()]
                else:
                    # Fallback: Look for capitalized words that could be company names
                    # Exclude common words like "What's", "The", etc.
                    exclude_words = {'what', 'whats', "what's", 'the', 'a', 'an', 'is', 'are', 'of', 'for', 'and', 'or', 'current', 'stock', 'price'}
                    
                    # Find all capitalized words
                    capitalized = re.findall(r'\b([A-Z][a-zA-Z]+)\b', query)
                    companies = [w for w in capitalized if w.lower() not in exclude_words]
                    
                    if companies:
                        params[param_name] = companies
                    else:
                        params[param_name] = []
            
            elif items_type in ["integer", "number", "float"]:
                # Extract all numbers
                numbers = re.findall(r'-?\d+(?:\.\d+)?', query)
                if items_type == "integer":
                    params[param_name] = [int(float(n)) for n in numbers]
                else:
                    params[param_name] = [float(n) for n in numbers]
        
        elif param_type == "integer":
            numbers = re.findall(r'-?\d+', query)
            if numbers:
                params[param_name] = int(numbers[0])
        
        elif param_type in ["number", "float"]:
            numbers = re.findall(r'-?\d+(?:\.\d+)?', query)
            if numbers:
                params[param_name] = float(numbers[0])
        
        elif param_type == "string":
            # For string params, try to extract relevant text
            # Look for quoted strings first
            quoted = re.findall(r'"([^"]+)"|\'([^\']+)\'', query)
            if quoted:
                params[param_name] = quoted[0][0] or quoted[0][1]
            else:
                # Try to extract based on common patterns
                match = re.search(r'(?:for|of|about|named?)\s+([A-Za-z\s]+?)(?:\s+(?:and|with|,)|[?.]|$)', query, re.IGNORECASE)
                if match:
                    params[param_name] = match.group(1).strip()
    
    return {func_name: params}
