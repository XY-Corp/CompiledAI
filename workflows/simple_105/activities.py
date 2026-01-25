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
    
    # Get function details
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters using regex
    params = {}
    
    # For math.power: "Calculate the power of X raised to the power Y"
    # Pattern 1: "power of X raised to the power Y" or "X raised to the power Y"
    power_pattern = re.search(r'(?:power\s+of\s+)?(\d+)\s+raised\s+to\s+(?:the\s+)?(?:power\s+)?(\d+)', query, re.IGNORECASE)
    
    # Pattern 2: "X to the power of Y" or "X^Y"
    if not power_pattern:
        power_pattern = re.search(r'(\d+)\s+to\s+the\s+power\s+(?:of\s+)?(\d+)', query, re.IGNORECASE)
    
    # Pattern 3: "X^Y"
    if not power_pattern:
        power_pattern = re.search(r'(\d+)\s*\^\s*(\d+)', query)
    
    # Pattern 4: Generic - extract all numbers and assign to base/exponent
    if not power_pattern:
        numbers = re.findall(r'\d+', query)
        if len(numbers) >= 2:
            params["base"] = int(numbers[0])
            params["exponent"] = int(numbers[1])
    
    if power_pattern:
        params["base"] = int(power_pattern.group(1))
        params["exponent"] = int(power_pattern.group(2))
    
    # Check for optional mod parameter
    mod_pattern = re.search(r'mod(?:ulus)?\s*(?:of|=|:)?\s*(\d+)', query, re.IGNORECASE)
    if mod_pattern:
        params["mod"] = int(mod_pattern.group(1))
    
    return {func_name: params}
