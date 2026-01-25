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
    """Extract function name and parameters from user query based on function schema.
    
    Returns format: {"function_name": {"param1": val1, "param2": val2}}
    """
    # Parse prompt - may be JSON string with nested structure
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
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_type == "boolean":
            # Look for boolean indicators in the query
            query_lower = query.lower()
            
            # Check for explicit mentions related to the parameter
            if "dissent" in param_name.lower() or "dissent" in param_desc:
                # Look for "include dissent" or similar patterns
                if re.search(r'include\s+dissent|with\s+dissent|dissent\s+information|dissenting', query_lower):
                    params[param_name] = True
                elif re.search(r'no\s+dissent|without\s+dissent|exclude\s+dissent', query_lower):
                    params[param_name] = False
                else:
                    # Default to False if not mentioned
                    params[param_name] = False
            else:
                # Generic boolean detection
                if re.search(rf'include\s+{param_name}|with\s+{param_name}', query_lower):
                    params[param_name] = True
                else:
                    params[param_name] = False
        
        elif param_type == "string":
            # Extract string values based on context
            if "title" in param_name.lower() or "case" in param_desc:
                # Look for case title patterns like "Roe v. Wade", "Brown v. Board of Education"
                # Pattern: Word(s) v. Word(s) - handles various case name formats
                case_match = re.search(r"['\"]?([A-Z][a-zA-Z]*(?:\s+[A-Z][a-zA-Z]*)?\s+v\.?\s+[A-Z][a-zA-Z]*(?:\s+[a-zA-Z]+)*)['\"]?", query)
                if case_match:
                    params[param_name] = case_match.group(1).strip("'\"")
                else:
                    # Try to find quoted strings
                    quoted_match = re.search(r"['\"]([^'\"]+)['\"]", query)
                    if quoted_match:
                        params[param_name] = quoted_match.group(1)
                    else:
                        # Fallback: look for "titled X" or "case X"
                        titled_match = re.search(r"(?:titled|called|named)\s+['\"]?([^'\".,]+)['\"]?", query, re.IGNORECASE)
                        if titled_match:
                            params[param_name] = titled_match.group(1).strip()
            else:
                # Generic string extraction - look for quoted values or after "of/for/with"
                quoted_match = re.search(r"['\"]([^'\"]+)['\"]", query)
                if quoted_match:
                    params[param_name] = quoted_match.group(1)
                else:
                    # Try pattern matching for common phrases
                    pattern_match = re.search(rf"(?:for|of|with)\s+([A-Za-z\s]+?)(?:\s*[.,]|\s+(?:and|with|include)|$)", query, re.IGNORECASE)
                    if pattern_match:
                        params[param_name] = pattern_match.group(1).strip()
        
        elif param_type in ["integer", "number", "float"]:
            # Extract numbers
            numbers = re.findall(r'\d+(?:\.\d+)?', query)
            if numbers:
                if param_type == "integer":
                    params[param_name] = int(numbers[0])
                else:
                    params[param_name] = float(numbers[0])
    
    return {func_name: params}
