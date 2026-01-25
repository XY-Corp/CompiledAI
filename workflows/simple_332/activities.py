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
    """Extract function name and parameters from user query using regex and string matching."""
    
    # Parse prompt - may be JSON string with nested structure
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
            # Handle BFCL format: {"question": [[{"role": "user", "content": "..."}]], ...}
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
    
    # Get function details
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters from query using regex and string matching
    params = {}
    query_lower = query.lower()
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_name == "player_name":
            # Extract player name - look for proper nouns (capitalized words)
            # Common patterns: "rating of X", "X's rating", "player X"
            
            # Pattern 1: "of [Name]" or "for [Name]"
            name_match = re.search(r'(?:of|for)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)', query)
            if name_match:
                params[param_name] = name_match.group(1)
                continue
            
            # Pattern 2: "[Name]'s" (possessive)
            name_match = re.search(r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)'s", query)
            if name_match:
                params[param_name] = name_match.group(1)
                continue
            
            # Pattern 3: Find all capitalized name sequences (excluding common words)
            exclude_words = {'what', 'the', 'is', 'of', 'for', 'in', 'a', 'an', 'chess', 'rating', 'classical', 'blitz', 'bullet', 'rapid'}
            name_parts = re.findall(r'\b([A-Z][a-z]+)\b', query)
            name_parts = [p for p in name_parts if p.lower() not in exclude_words]
            if name_parts:
                params[param_name] = ' '.join(name_parts)
        
        elif param_name == "variant":
            # Extract chess variant - look for known variants
            variants = ['classical', 'blitz', 'bullet', 'rapid', 'standard']
            for variant in variants:
                if variant in query_lower:
                    params[param_name] = variant
                    break
            # If no variant found but it's not required, we can skip or use default
            if param_name not in params:
                # Check if mentioned in query context
                if 'classical' in query_lower:
                    params[param_name] = 'classical'
                elif 'blitz' in query_lower:
                    params[param_name] = 'blitz'
                elif 'bullet' in query_lower:
                    params[param_name] = 'bullet'
                elif 'rapid' in query_lower:
                    params[param_name] = 'rapid'
                else:
                    # Default to classical as per function description
                    params[param_name] = 'classical'
        
        elif param_type in ["integer", "number", "float"]:
            # Extract numbers
            numbers = re.findall(r'\d+(?:\.\d+)?', query)
            if numbers:
                if param_type == "integer":
                    params[param_name] = int(numbers[0])
                else:
                    params[param_name] = float(numbers[0])
        
        elif param_type == "string":
            # Generic string extraction - try common patterns
            # Pattern: "param_name X" or "param_name: X" or "param_name is X"
            pattern = rf'{param_name}[:\s]+["\']?([^"\']+)["\']?'
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                params[param_name] = match.group(1).strip()
    
    return {func_name: params}
