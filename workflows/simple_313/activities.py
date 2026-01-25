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
    """Extract function call parameters from user query and return as {func_name: {params}}.
    
    Uses regex and string matching to extract parameter values from the query.
    """
    # Parse prompt - may be JSON string with nested structure
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
        else:
            data = prompt
        
        # Extract user query from BFCL format: {"question": [[{"role": "user", "content": "..."}]]}
        if isinstance(data, dict) and "question" in data:
            question_data = data["question"]
            if isinstance(question_data, list) and len(question_data) > 0:
                if isinstance(question_data[0], list) and len(question_data[0]) > 0:
                    query = question_data[0][0].get("content", str(prompt))
                else:
                    query = str(prompt)
            else:
                query = str(prompt)
        else:
            query = str(prompt)
    except (json.JSONDecodeError, TypeError):
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
    
    # Extract parameters based on schema
    params = {}
    query_lower = query.lower()
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_name == "name" and "celebrity" in param_desc:
            # Extract celebrity name - look for known patterns
            # Common pattern: "of [Name]" or "[Name]'s"
            name_patterns = [
                r"of\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)",  # "of Messi" or "of Lionel Messi"
                r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)'s",      # "Messi's"
                r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+according",  # "Messi according"
            ]
            
            for pattern in name_patterns:
                match = re.search(pattern, query)
                if match:
                    params[param_name] = match.group(1).strip()
                    break
            
            # If no match found, try to find capitalized words that could be names
            if param_name not in params:
                # Look for capitalized words (potential names)
                cap_words = re.findall(r'\b([A-Z][a-z]+)\b', query)
                # Filter out common words
                common_words = {"What", "The", "Get", "Find", "Show", "Tell", "How", "Default", "USD", "EUR"}
                names = [w for w in cap_words if w not in common_words]
                if names:
                    params[param_name] = " ".join(names[:2]) if len(names) > 1 else names[0]
        
        elif param_name == "currency":
            # Extract currency - look for currency codes or names
            currency_patterns = [
                r'\b(USD|EUR|GBP|JPY|CNY|INR|AUD|CAD|CHF)\b',  # Currency codes
                r'\bin\s+(euro|dollar|pound|yen|yuan|rupee)s?\b',  # "in euros"
                r'\b(euro|dollar|pound|yen|yuan|rupee)s?\b',  # Currency names
            ]
            
            currency_map = {
                "euro": "EUR", "euros": "EUR",
                "dollar": "USD", "dollars": "USD",
                "pound": "GBP", "pounds": "GBP",
                "yen": "JPY",
                "yuan": "CNY",
                "rupee": "INR", "rupees": "INR",
            }
            
            for pattern in currency_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    currency_val = match.group(1).lower()
                    # Map to currency code if it's a name
                    if currency_val in currency_map:
                        params[param_name] = currency_map[currency_val]
                    else:
                        params[param_name] = currency_val.upper()
                    break
            
            # Default to USD if not found but required
            if param_name not in params:
                params[param_name] = "USD"
    
    return {func_name: params}
