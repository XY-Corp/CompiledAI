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
    
    # Parse functions (may be JSON string)
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
    
    params = {}
    
    # Extract indexes (array of strings) - look for known index names
    if "indexes" in props:
        known_indexes = ["S&P 500", "Dow Jones", "NASDAQ", "FTSE 100", "DAX"]
        found_indexes = []
        query_lower = query.lower()
        
        for idx in known_indexes:
            # Check for exact match or common variations
            idx_lower = idx.lower()
            if idx_lower in query_lower:
                found_indexes.append(idx)
            # Handle "S&P" without "500"
            elif idx == "S&P 500" and ("s&p" in query_lower or "s & p" in query_lower):
                found_indexes.append(idx)
            # Handle "Dow" without "Jones"
            elif idx == "Dow Jones" and "dow" in query_lower:
                found_indexes.append(idx)
        
        if found_indexes:
            params["indexes"] = found_indexes
    
    # Extract days (integer) - look for number followed by "day(s)"
    if "days" in props:
        # Pattern: "X days" or "past X days" or "last X days"
        days_patterns = [
            r'(?:past|last|over the past|over the last)\s+(\d+)\s+days?',
            r'(\d+)\s+days?\s+(?:ago|back|period)',
            r'(\d+)\s+days?',
        ]
        
        for pattern in days_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                params["days"] = int(match.group(1))
                break
    
    # Extract detailed (boolean) - only if explicitly mentioned
    if "detailed" in props:
        # Check if user explicitly asks for detailed data
        detailed_patterns = [
            r'\bdetailed\b',
            r'\bhigh\s+(?:and\s+)?low\b',
            r'\bopening\s+(?:and\s+)?closing\b',
            r'\bfull\s+data\b',
        ]
        
        for pattern in detailed_patterns:
            if re.search(pattern, query, re.IGNORECASE):
                params["detailed"] = True
                break
        # Don't include if not explicitly requested (optional param with default)
    
    return {func_name: params}
