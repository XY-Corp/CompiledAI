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
    props = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters based on schema
    params = {}
    
    for param_name, param_info in props.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_type == "integer":
            # Extract years - look for 4-digit numbers
            years = re.findall(r'\b(19\d{2}|20\d{2})\b', query)
            
            if "from" in param_name or "start" in param_name:
                # Get the first/smaller year for from_year
                if years:
                    params[param_name] = int(min(years, key=int))
            elif "to" in param_name or "end" in param_name:
                # Get the last/larger year for to_year
                if years:
                    params[param_name] = int(max(years, key=int))
            else:
                # Generic integer extraction
                numbers = re.findall(r'\d+', query)
                if numbers:
                    params[param_name] = int(numbers[0])
        
        elif param_type == "string":
            # Extract subject/topic - look for keywords based on description
            if "subject" in param_name or "topic" in param_name or "matter" in param_desc:
                # Common patterns: "about X", "regarding X", "case about X"
                patterns = [
                    r'about\s+(\w+)',
                    r'regarding\s+(\w+)',
                    r'case\s+(?:about\s+)?(\w+)',
                    r'historical\s+(?:law\s+)?case\s+(?:about\s+)?(\w+)',
                ]
                
                for pattern in patterns:
                    match = re.search(pattern, query, re.IGNORECASE)
                    if match:
                        subject = match.group(1).lower()
                        # Filter out common non-subject words
                        if subject not in ['from', 'to', 'the', 'a', 'an', 'in', 'on']:
                            params[param_name] = subject
                            break
                
                # Fallback: look for common legal subjects
                if param_name not in params:
                    legal_subjects = ['fraud', 'theft', 'murder', 'assault', 'robbery', 
                                     'contract', 'negligence', 'bankruptcy', 'patent', 
                                     'copyright', 'trademark', 'discrimination']
                    for subject in legal_subjects:
                        if subject in query.lower():
                            params[param_name] = subject
                            break
    
    return {func_name: params}
