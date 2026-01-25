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
    
    # Parse prompt (may be JSON string with nested structure)
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
    props = func.get("parameters", {}).get("properties", {})
    
    params = {}
    query_lower = query.lower()
    
    # Extract company name - look for patterns like "company 'X'" or "related to X"
    company_match = re.search(r"company\s+['\"]([^'\"]+)['\"]", query, re.IGNORECASE)
    if not company_match:
        company_match = re.search(r"related to\s+(?:the\s+)?(?:company\s+)?['\"]?([A-Z][a-zA-Z]+)['\"]?", query, re.IGNORECASE)
    if company_match:
        params["company"] = company_match.group(1)
    
    # Extract date - look for patterns like "after January 1, 2021" or "filed after MM-DD-YYYY"
    date_match = re.search(r"(?:after|since|from)\s+(\w+)\s+(\d{1,2}),?\s+(\d{4})", query, re.IGNORECASE)
    if date_match:
        month_name = date_match.group(1)
        day = date_match.group(2)
        year = date_match.group(3)
        
        # Convert month name to number
        months = {
            "january": "01", "february": "02", "march": "03", "april": "04",
            "may": "05", "june": "06", "july": "07", "august": "08",
            "september": "09", "october": "10", "november": "11", "december": "12"
        }
        month_num = months.get(month_name.lower(), "01")
        # Format as MM-DD-YYYY
        params["start_date"] = f"{month_num}-{day.zfill(2)}-{year}"
    
    # Extract location - look for state names
    states = [
        "Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado",
        "Connecticut", "Delaware", "Florida", "Georgia", "Hawaii", "Idaho",
        "Illinois", "Indiana", "Iowa", "Kansas", "Kentucky", "Louisiana",
        "Maine", "Maryland", "Massachusetts", "Michigan", "Minnesota",
        "Mississippi", "Missouri", "Montana", "Nebraska", "Nevada",
        "New Hampshire", "New Jersey", "New Mexico", "New York",
        "North Carolina", "North Dakota", "Ohio", "Oklahoma", "Oregon",
        "Pennsylvania", "Rhode Island", "South Carolina", "South Dakota",
        "Tennessee", "Texas", "Utah", "Vermont", "Virginia", "Washington",
        "West Virginia", "Wisconsin", "Wyoming"
    ]
    
    for state in states:
        if state.lower() in query_lower:
            params["location"] = state
            break
    
    # Extract status - look for enum values
    status_values = ["ongoing", "settled", "dismissed"]
    for status in status_values:
        if status in query_lower:
            params["status"] = status
            break
    
    return {func_name: params}
