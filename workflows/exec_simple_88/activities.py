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
    """Extract function call parameters from natural language query using regex and pattern matching."""
    
    # Parse prompt - may be JSON string with nested structure
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
            # Handle BFCL format: {"question": [[{"role": "user", "content": "..."}]], "function": [...]}
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
    
    if not funcs:
        return {"error": "No functions provided"}
    
    func = funcs[0]
    func_name = func.get("name", "")
    props = func.get("parameters", {}).get("properties", {})
    
    params = {}
    query_lower = query.lower()
    
    # Extract weight (kilograms)
    weight_patterns = [
        r'weigh(?:s|ing)?\s+(?:about\s+)?(\d+(?:\.\d+)?)\s*(?:kg|kilo|kilograms?)?',
        r'(\d+(?:\.\d+)?)\s*(?:kg|kilo|kilograms?)',
        r'weight\s*(?:is|of)?\s*(?:about\s+)?(\d+(?:\.\d+)?)',
    ]
    for pattern in weight_patterns:
        match = re.search(pattern, query_lower)
        if match:
            params["weight"] = float(match.group(1))
            break
    
    # Extract height (centimeters)
    height_patterns = [
        r'(\d+(?:\.\d+)?)\s*(?:cm|centimeters?)\s*tall',
        r'(\d+(?:\.\d+)?)\s*(?:cm|centimeters?)',
        r'height\s*(?:is|of)?\s*(?:about\s+)?(\d+(?:\.\d+)?)',
        r"i'm\s+(\d+(?:\.\d+)?)\s*(?:cm|centimeters?)",
    ]
    for pattern in height_patterns:
        match = re.search(pattern, query_lower)
        if match:
            params["height"] = float(match.group(1))
            break
    
    # Extract age (years)
    age_patterns = [
        r'(\d+)[\s-]*year[\s-]*old',
        r'age\s*(?:is|of)?\s*(\d+)',
        r"i'm\s+(?:a\s+)?(\d+)",
    ]
    for pattern in age_patterns:
        match = re.search(pattern, query_lower)
        if match:
            params["age"] = float(match.group(1))
            break
    
    # Extract gender
    if re.search(r'\b(?:male|man|guy|gentleman)\b', query_lower):
        params["gender"] = "male"
    elif re.search(r'\b(?:female|woman|lady|girl)\b', query_lower):
        params["gender"] = "female"
    else:
        params["gender"] = "other"
    
    # Extract activity level (1-5)
    activity_patterns = [
        r'activity\s*level\s*(?:is|of)?\s*(?:about\s+)?(?:pretty\s+)?(?:low\s*,?\s*)?(?:around\s+)?(\d)',
        r'level\s*(?:is)?\s*(?:around\s+)?(\d)',
        r'activity\s*(?:level)?\s*(?:is)?\s*(\d)',
    ]
    for pattern in activity_patterns:
        match = re.search(pattern, query_lower)
        if match:
            level = int(match.group(1))
            if 1 <= level <= 5:
                params["activity_level"] = level
                break
    
    # Fallback: check for descriptive activity levels
    if "activity_level" not in params:
        if re.search(r'\b(?:sedentary|very\s+low|not\s+active|pretty\s+low)\b', query_lower):
            params["activity_level"] = 1
        elif re.search(r'\blightly?\s+active\b', query_lower):
            params["activity_level"] = 2
        elif re.search(r'\bmoderately?\s+active\b', query_lower):
            params["activity_level"] = 3
        elif re.search(r'\bvery\s+active\b', query_lower):
            params["activity_level"] = 4
        elif re.search(r'\bextremely?\s+active\b', query_lower):
            params["activity_level"] = 5
    
    # Extract goal
    if re.search(r'\b(?:lose|losing|weight\s+loss|slim|cut)\b', query_lower):
        params["goal"] = "lose"
    elif re.search(r'\b(?:gain|gaining|bulk|build)\b', query_lower):
        params["goal"] = "gain"
    elif re.search(r'\b(?:maintain|maintaining|keep)\b', query_lower):
        params["goal"] = "maintain"
    
    return {func_name: params}
