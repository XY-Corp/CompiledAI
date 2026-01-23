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
    
    # Get function details
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters based on schema
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        
        if param_name == "act_name":
            # Extract act name - look for patterns like "X Act" or "X Amendment Act"
            # Pattern: capture text before "of YYYY" or the full act name
            act_patterns = [
                r'details of (?:the )?(.+?(?:Act|Bill|Law))',  # "details of X Act"
                r'about (?:the )?(.+?(?:Act|Bill|Law))',  # "about X Act"
                r'(?:the )?(.+?(?:Act|Bill|Law))',  # fallback: any "X Act"
            ]
            
            for pattern in act_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    act_name = match.group(1).strip()
                    # Remove trailing "of YYYY" if present
                    act_name = re.sub(r'\s+of\s+\d{4}\.?$', '', act_name, flags=re.IGNORECASE)
                    # Clean up any trailing punctuation
                    act_name = act_name.rstrip('.')
                    params["act_name"] = act_name
                    break
        
        elif param_name == "amendment_year":
            # Extract year - look for 4-digit numbers (years)
            year_patterns = [
                r'of\s+(\d{4})',  # "of 2013"
                r'in\s+(\d{4})',  # "in 2013"
                r'(\d{4})\s+amendment',  # "2013 amendment"
                r'amendment.*?(\d{4})',  # "amendment ... 2013"
                r'(\d{4})',  # fallback: any 4-digit year
            ]
            
            for pattern in year_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    year_str = match.group(1)
                    # Validate it's a reasonable year (1800-2100)
                    year = int(year_str)
                    if 1800 <= year <= 2100:
                        params["amendment_year"] = year
                        break
    
    return {func_name: params}
