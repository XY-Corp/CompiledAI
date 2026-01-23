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
    """Extract function call parameters from natural language query.
    
    Parses the user query and function schema to extract parameter values
    using regex and string matching - no LLM calls needed.
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
    
    # Extract parameters from query
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_type == "integer" or param_type == "number":
            # Extract numbers based on context clues in description
            if "radius" in param_desc or "distance" in param_desc or "kilometer" in param_desc:
                # Look for patterns like "50km", "50 km", "within 50"
                radius_match = re.search(r'(\d+)\s*(?:km|kilometer|kilometres?)', query, re.IGNORECASE)
                if radius_match:
                    params[param_name] = int(radius_match.group(1))
                else:
                    # Try "within X" pattern
                    within_match = re.search(r'within\s+(\d+)', query, re.IGNORECASE)
                    if within_match:
                        params[param_name] = int(within_match.group(1))
            elif "amount" in param_desc or "number" in param_desc or "count" in param_desc:
                # Look for patterns like "5 tallest", "top 10", "find 3"
                amount_match = re.search(r'(?:find|get|show|list|top|the)\s*(?:me\s+)?(?:the\s+)?(\d+)', query, re.IGNORECASE)
                if amount_match:
                    params[param_name] = int(amount_match.group(1))
                else:
                    # Try "X tallest/highest/largest" pattern
                    count_match = re.search(r'(\d+)\s+(?:tallest|highest|largest|biggest|nearest|closest)', query, re.IGNORECASE)
                    if count_match:
                        params[param_name] = int(count_match.group(1))
            else:
                # Generic number extraction - get first unmatched number
                all_numbers = re.findall(r'\d+', query)
                used_numbers = [str(v) for v in params.values() if isinstance(v, int)]
                for num in all_numbers:
                    if num not in used_numbers:
                        params[param_name] = int(num)
                        break
        
        elif param_type == "string":
            # Extract string values based on context
            if "location" in param_desc or "city" in param_desc or "place" in param_desc:
                # Look for patterns like "of Denver", "near Denver", "in Denver, Colorado"
                location_patterns = [
                    r'(?:of|near|in|around|from)\s+([A-Z][a-zA-Z]+(?:,?\s+[A-Z][a-zA-Z]+)?)',
                    r'([A-Z][a-zA-Z]+,\s*[A-Z][a-zA-Z]+)',  # "Denver, Colorado"
                ]
                for pattern in location_patterns:
                    loc_match = re.search(pattern, query)
                    if loc_match:
                        params[param_name] = loc_match.group(1).strip()
                        break
    
    return {func_name: params}
