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
    """Extract function call parameters from user query using regex and string matching.
    
    Returns format: {"function_name": {"param1": val1, "param2": val2}}
    """
    # Parse prompt - may be JSON string with nested structure
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
            # Handle BFCL format: {"question": [[{"role": "user", "content": "..."}]]}
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

    # Extract parameters from query using regex and string matching
    params = {}

    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")

        if param_type == "string":
            # Extract location/city - look for patterns like "for X" or "in X"
            if param_name in ["location", "city", "place"]:
                # Pattern: "for City, Country" or "for City Country" or "in City"
                location_patterns = [
                    r'(?:for|in)\s+([A-Za-z\s]+,\s*[A-Za-z\s]+?)(?:\s+for|\s+with|\s+\d|$)',
                    r'(?:for|in)\s+([A-Za-z\s]+?)(?:\s+for|\s+with|\s+\d|$)',
                ]
                for pattern in location_patterns:
                    match = re.search(pattern, query, re.IGNORECASE)
                    if match:
                        params[param_name] = match.group(1).strip()
                        break

        elif param_type == "integer":
            # Extract numbers - look for patterns like "next N days" or "N days"
            if param_name in ["days", "num_days", "forecast_days"]:
                days_patterns = [
                    r'(?:next|for)\s+(\d+)\s+days?',
                    r'(\d+)\s+days?',
                ]
                for pattern in days_patterns:
                    match = re.search(pattern, query, re.IGNORECASE)
                    if match:
                        params[param_name] = int(match.group(1))
                        break
            else:
                # Generic number extraction
                numbers = re.findall(r'\d+', query)
                if numbers:
                    params[param_name] = int(numbers[0])

        elif param_type == "boolean":
            # Check for boolean indicators in query
            if param_name in ["details", "detailed", "verbose"]:
                # Look for keywords indicating true
                true_keywords = ["detail", "detailed", "verbose", "with details", "full"]
                params[param_name] = any(kw in query.lower() for kw in true_keywords)
            else:
                # Generic boolean - default to False unless explicitly mentioned
                params[param_name] = param_name.lower() in query.lower()

    return {func_name: params}
