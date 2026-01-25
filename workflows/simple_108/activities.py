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
    """Extract function call parameters from natural language prompt.
    
    Parses the user query and function schema to extract the appropriate
    function name and parameters using regex and string matching.
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
        
        if param_type == "array":
            # Extract array values - look for quoted strings in lists
            # Pattern: 'Age', 'Income' and 'Education' or "Age", "Income", "Education"
            # Also handles: predictor variables 'X', 'Y', 'Z'
            
            # Try to find quoted strings that appear to be list items
            quoted_items = re.findall(r"['\"]([^'\"]+)['\"]", query)
            
            # Filter based on context - for predictors, exclude target variable
            if param_name == "predictors":
                # Look for target variable pattern to exclude it
                target_match = re.search(r"target\s+(?:variable\s+)?['\"]?([^'\".,]+)['\"]?", query, re.IGNORECASE)
                target_var = target_match.group(1).strip() if target_match else None
                
                # Also check for "and a target variable 'X'" pattern
                target_match2 = re.search(r"and\s+a?\s*target\s+(?:variable\s+)?['\"]([^'\"]+)['\"]", query, re.IGNORECASE)
                if target_match2:
                    target_var = target_match2.group(1).strip()
                
                # Filter out the target variable from predictors
                if target_var and quoted_items:
                    params[param_name] = [item for item in quoted_items if item != target_var]
                elif quoted_items:
                    # If we can't identify target, take all but last (often target is mentioned last)
                    params[param_name] = quoted_items[:-1] if len(quoted_items) > 1 else quoted_items
                else:
                    params[param_name] = []
            else:
                params[param_name] = quoted_items if quoted_items else []
        
        elif param_type == "string":
            # Extract string value based on parameter name context
            if param_name == "target":
                # Look for target variable pattern
                # Patterns: "target variable 'X'" or "target variable X"
                target_patterns = [
                    r"target\s+(?:variable\s+)?['\"]([^'\"]+)['\"]",
                    r"target\s+(?:variable\s+)?(\w+)",
                ]
                
                for pattern in target_patterns:
                    match = re.search(pattern, query, re.IGNORECASE)
                    if match:
                        params[param_name] = match.group(1).strip()
                        break
            else:
                # Generic string extraction - look for quoted value after param name
                pattern = rf"{param_name}\s*[=:]\s*['\"]?([^'\".,]+)['\"]?"
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    params[param_name] = match.group(1).strip()
        
        elif param_type == "boolean":
            # Extract boolean based on keywords
            if param_name == "standardize":
                # Look for standardization keywords
                if re.search(r"\bstandardiz(?:e|ation)\b", query, re.IGNORECASE):
                    # Check if it's negated
                    if re.search(r"\b(?:no|without|don't|do not|disable)\s+standardiz", query, re.IGNORECASE):
                        params[param_name] = False
                    else:
                        params[param_name] = True
                # Also check for "apply standardization"
                elif re.search(r"apply\s+standardiz", query, re.IGNORECASE):
                    params[param_name] = True
            else:
                # Generic boolean - look for true/false or yes/no
                if re.search(rf"{param_name}\s*[=:]\s*(?:true|yes|1)", query, re.IGNORECASE):
                    params[param_name] = True
                elif re.search(rf"{param_name}\s*[=:]\s*(?:false|no|0)", query, re.IGNORECASE):
                    params[param_name] = False
        
        elif param_type in ["integer", "number", "float"]:
            # Extract numeric value
            pattern = rf"{param_name}\s*[=:]\s*(\d+(?:\.\d+)?)"
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                value = match.group(1)
                if param_type == "integer":
                    params[param_name] = int(value)
                else:
                    params[param_name] = float(value)
    
    return {func_name: params}
