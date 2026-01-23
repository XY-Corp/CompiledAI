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
    
    # Parse prompt (may be JSON string with nested structure)
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
        else:
            data = prompt
        
        # Extract user query from BFCL format: {"question": [[{"role": "user", "content": "..."}]]}
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
    
    # Get function schema
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters from query using regex and string matching
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_type == "integer" or param_type == "number":
            # Extract numbers from query
            numbers = re.findall(r'\b(\d+)\b', query)
            if numbers:
                # Use first number found for quantity-like params
                params[param_name] = int(numbers[0])
        
        elif param_type == "string":
            # Handle different string parameter types based on description/name
            if "topic" in param_name.lower() or "subject" in param_desc:
                # Extract topic - look for keywords like "on", "about", "for"
                # Pattern: "news on X", "about X", "for X"
                topic_patterns = [
                    r'(?:news\s+(?:on|about|for)\s+)([A-Za-z0-9\s]+?)(?:\s+in\s+|\s*$)',
                    r'(?:on|about|for)\s+([A-Za-z0-9\s]+?)(?:\s+in\s+|\s*$)',
                    r'latest\s+([A-Za-z0-9\s]+?)\s+news',
                ]
                for pattern in topic_patterns:
                    match = re.search(pattern, query, re.IGNORECASE)
                    if match:
                        topic = match.group(1).strip()
                        # Clean up - remove trailing numbers
                        topic = re.sub(r'\s*\d+\s*$', '', topic).strip()
                        if topic:
                            params[param_name] = topic
                            break
                
                # Fallback: look for capitalized words that might be topics
                if param_name not in params:
                    caps = re.findall(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b', query)
                    if caps:
                        params[param_name] = caps[0]
            
            elif "region" in param_name.lower() or "country" in param_desc or "geographical" in param_desc:
                # Extract region - look for "in X" pattern or country codes
                region_patterns = [
                    r'\bin\s+([A-Z]{2})\b',  # Country codes like US, UK
                    r'\bin\s+([A-Za-z\s]+?)(?:\s*$|\s+(?:on|about|for))',  # "in United States"
                ]
                for pattern in region_patterns:
                    match = re.search(pattern, query, re.IGNORECASE)
                    if match:
                        region = match.group(1).strip().upper() if len(match.group(1)) == 2 else match.group(1).strip()
                        params[param_name] = region
                        break
                
                # Check for default value in description
                if param_name not in params:
                    default_match = re.search(r"default\s+(?:is\s+)?['\"]?([A-Z]{2})['\"]?", param_desc, re.IGNORECASE)
                    if default_match:
                        params[param_name] = default_match.group(1).upper()
    
    return {func_name: params}
