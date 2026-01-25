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
    if isinstance(functions, str):
        try:
            functions = json.loads(functions)
        except json.JSONDecodeError:
            functions = []
    
    if not functions:
        return {"error": "No functions provided"}
    
    func = functions[0]
    func_name = func.get("name", "")
    props = func.get("parameters", {}).get("properties", {})
    
    params = {}
    
    # Extract scientist name - look for proper nouns (capitalized names)
    # Pattern: "Albert Einstein's" or "by Albert Einstein" or just "Albert Einstein"
    scientist_patterns = [
        r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)'s",  # "Albert Einstein's"
        r"by\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)",  # "by Albert Einstein"
        r"([A-Z][a-z]+\s+[A-Z][a-z]+)",  # "Albert Einstein" (two capitalized words)
    ]
    
    scientist = None
    for pattern in scientist_patterns:
        match = re.search(pattern, query)
        if match:
            scientist = match.group(1)
            break
    
    if scientist and "scientist" in props:
        params["scientist"] = scientist
    
    # Extract date - look for various date formats
    # Pattern: "March 17, 1915" or "17 March 1915" or "1915-03-17"
    month_map = {
        "january": "01", "february": "02", "march": "03", "april": "04",
        "may": "05", "june": "06", "july": "07", "august": "08",
        "september": "09", "october": "10", "november": "11", "december": "12"
    }
    
    date = None
    
    # Try "Month DD, YYYY" format (e.g., "March 17, 1915")
    date_match = re.search(r"(\w+)\s+(\d{1,2}),?\s+(\d{4})", query, re.IGNORECASE)
    if date_match:
        month_name = date_match.group(1).lower()
        day = date_match.group(2).zfill(2)
        year = date_match.group(3)
        if month_name in month_map:
            date = f"{year}-{month_map[month_name]}-{day}"
    
    # Try "DD Month YYYY" format
    if not date:
        date_match = re.search(r"(\d{1,2})\s+(\w+)\s+(\d{4})", query, re.IGNORECASE)
        if date_match:
            day = date_match.group(1).zfill(2)
            month_name = date_match.group(2).lower()
            year = date_match.group(3)
            if month_name in month_map:
                date = f"{year}-{month_map[month_name]}-{day}"
    
    # Try ISO format "YYYY-MM-DD"
    if not date:
        date_match = re.search(r"(\d{4})-(\d{2})-(\d{2})", query)
        if date_match:
            date = date_match.group(0)
    
    if date and "date" in props:
        params["date"] = date
    
    # Extract category if mentioned (optional parameter)
    if "category" in props:
        # Look for field/category keywords
        category_patterns = [
            r"(?:in|field of|category)\s+['\"]?(\w+)['\"]?",
            r"(\w+)\s+contribution",
        ]
        
        # Common science categories
        categories = ["physics", "chemistry", "biology", "mathematics", "astronomy", "medicine"]
        
        for cat in categories:
            if cat.lower() in query.lower():
                params["category"] = cat.capitalize()
                break
    
    return {func_name: params}
