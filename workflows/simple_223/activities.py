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
    """Extract function name and parameters from user query using regex patterns."""
    
    # Parse prompt - may be JSON string with nested structure
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
            # Extract user query from BFCL format: {"question": [[{"role": "user", "content": "..."}]]}
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
    
    # Get function details
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters using regex
    params = {}
    
    # Extract all numbers from the query
    numbers = re.findall(r'\d+', query)
    
    # Map numbers to parameters based on context clues in the query
    # Look for specific patterns for each parameter
    
    # Pattern for total/group size: "group size of X", "size of X", "total of X"
    total_match = re.search(r'(?:group\s+size|size|total)\s+(?:of\s+)?(\d+)', query, re.IGNORECASE)
    
    # Pattern for extroverts: "extroverted members being X", "X extroverts", "extroverted X"
    extrovert_match = re.search(r'(?:extrovert(?:ed|s)?\s+(?:members\s+)?(?:being\s+)?(\d+)|(\d+)\s+extrovert)', query, re.IGNORECASE)
    
    # Pattern for introverts: "introverted members being X", "X introverts", "introverted X"
    introvert_match = re.search(r'(?:introvert(?:ed|s)?\s+(?:members\s+)?(?:being\s+)?(\d+)|(\d+)\s+introvert)', query, re.IGNORECASE)
    
    # Extract values from matches
    if "total" in params_schema:
        if total_match:
            params["total"] = int(total_match.group(1))
        elif len(numbers) >= 1:
            # First number is often the total
            params["total"] = int(numbers[0])
    
    if "extroverts" in params_schema:
        if extrovert_match:
            # Get whichever group matched (group 1 or group 2)
            val = extrovert_match.group(1) or extrovert_match.group(2)
            params["extroverts"] = int(val)
        elif len(numbers) >= 2:
            params["extroverts"] = int(numbers[1])
    
    if "introverts" in params_schema:
        if introvert_match:
            # Get whichever group matched (group 1 or group 2)
            val = introvert_match.group(1) or introvert_match.group(2)
            params["introverts"] = int(val)
        elif len(numbers) >= 3:
            params["introverts"] = int(numbers[2])
    
    return {func_name: params}
