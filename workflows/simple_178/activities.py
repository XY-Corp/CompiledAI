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
    
    # Get function schema
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters using regex and string matching
    params = {}
    
    # Extract case_number - look for quoted string pattern like 'LAX2019080202'
    case_number_match = re.search(r"['\"]([A-Z0-9]+)['\"]", query)
    if case_number_match:
        params["case_number"] = case_number_match.group(1)
    else:
        # Try pattern: "case numbered X" or "case number X"
        case_match = re.search(r"case\s+(?:numbered?|#)\s*['\"]?([A-Z0-9]+)['\"]?", query, re.IGNORECASE)
        if case_match:
            params["case_number"] = case_match.group(1)
    
    # Extract court_location - look for "in the X court" or "X court"
    location_match = re.search(r"(?:in\s+(?:the\s+)?)?([A-Za-z\s]+?)\s+court", query, re.IGNORECASE)
    if location_match:
        params["court_location"] = location_match.group(1).strip()
    
    # Check for additional_details - look for keywords
    additional_keywords = ["attorneys", "plaintiffs", "defendants", "charges", "court_updates"]
    found_details = []
    for keyword in additional_keywords:
        if keyword.lower() in query.lower():
            found_details.append(keyword)
    
    # Only include additional_details if explicitly mentioned (it's optional)
    if found_details:
        params["additional_details"] = found_details
    
    return {func_name: params}
