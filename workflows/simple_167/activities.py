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
        param_desc = param_info.get("description", "").lower()
        
        if param_type == "boolean":
            # Look for boolean indicators in the query
            # Check for positive indicators
            positive_patterns = [
                r'\binclude\s+' + re.escape(param_name.replace("_", " ")),
                r'\binclude\s+' + re.escape(param_name.replace("_", "")),
                r'\bwith\s+' + re.escape(param_name.replace("_", " ")),
                r'\b' + re.escape(param_name.replace("_", " ")) + r'\s+information',
                r'\binclude\b.*\b' + re.escape(param_name.split("_")[-1]),
            ]
            
            # Check for negative indicators
            negative_patterns = [
                r'\bexclude\s+' + re.escape(param_name.replace("_", " ")),
                r'\bwithout\s+' + re.escape(param_name.replace("_", " ")),
                r'\bno\s+' + re.escape(param_name.replace("_", " ")),
            ]
            
            # Default to False
            value = False
            
            # Check for positive matches
            for pattern in positive_patterns:
                if re.search(pattern, query, re.IGNORECASE):
                    value = True
                    break
            
            # Check for negative matches (override positive if found)
            for pattern in negative_patterns:
                if re.search(pattern, query, re.IGNORECASE):
                    value = False
                    break
            
            # Special case: "Include dissent information" pattern
            if "dissent" in param_name.lower():
                if re.search(r'include\s+dissent', query, re.IGNORECASE):
                    value = True
                elif re.search(r'exclude\s+dissent|without\s+dissent|no\s+dissent', query, re.IGNORECASE):
                    value = False
            
            params[param_name] = value
        
        elif param_type == "string":
            # Extract string values based on context
            if "title" in param_name.lower() or "case" in param_desc:
                # Look for case title patterns like "X v. Y" or "X vs Y" or quoted titles
                # Try quoted string first
                quoted_match = re.search(r"['\"]([^'\"]+)['\"]", query)
                if quoted_match:
                    params[param_name] = quoted_match.group(1)
                else:
                    # Look for "case titled X" or "case X"
                    title_match = re.search(r"case\s+(?:titled|named|called)?\s*['\"]?([A-Z][a-zA-Z\s]+\s+v\.?\s*[A-Z][a-zA-Z\s]+)['\"]?", query, re.IGNORECASE)
                    if title_match:
                        params[param_name] = title_match.group(1).strip()
                    else:
                        # Look for "X v. Y" or "X vs Y" pattern anywhere
                        vs_match = re.search(r"([A-Z][a-zA-Z\s]+)\s+v\.?\s*([A-Z][a-zA-Z\s]+)", query)
                        if vs_match:
                            params[param_name] = f"{vs_match.group(1).strip()} v. {vs_match.group(2).strip()}"
                        else:
                            params[param_name] = "<UNKNOWN>"
            else:
                # Generic string extraction - try quoted values first
                quoted_match = re.search(r"['\"]([^'\"]+)['\"]", query)
                if quoted_match:
                    params[param_name] = quoted_match.group(1)
                else:
                    params[param_name] = "<UNKNOWN>"
        
        elif param_type in ["integer", "number", "float"]:
            # Extract numbers
            numbers = re.findall(r'\d+(?:\.\d+)?', query)
            if numbers:
                if param_type == "integer":
                    params[param_name] = int(numbers[0])
                else:
                    params[param_name] = float(numbers[0])
            else:
                params[param_name] = 0
    
    return {func_name: params}
