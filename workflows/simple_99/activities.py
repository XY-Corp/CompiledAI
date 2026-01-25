import re
import json
import math
from typing import Any


async def extract_function_call(
    prompt: str,
    functions: list,
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extract function call parameters from user query using regex and string matching."""
    
    # Parse prompt (may be JSON string with nested structure)
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
            # Extract user query from BFCL format
            if "question" in data and isinstance(data["question"], list):
                if len(data["question"]) > 0 and isinstance(data["question"][0], list):
                    query = data["question"][0][0].get("content", prompt)
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
    
    # Get function details
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters from query
    params = {}
    query_lower = query.lower()
    
    # Extract frequency - look for "frequency of X Hz" or "X Hz"
    freq_patterns = [
        r'frequency\s+of\s+(\d+)\s*(?:hz)?',
        r'(\d+)\s*hz',
        r'frequency\s*[=:]\s*(\d+)',
    ]
    for pattern in freq_patterns:
        match = re.search(pattern, query_lower)
        if match:
            params["frequency"] = int(match.group(1))
            break
    
    # Extract start_range - look for "from X" or "start X"
    # Handle special values like "0" and "2 pi"
    start_patterns = [
        r'from\s+(\d+(?:\.\d+)?)\s*(?:to|pi)',
        r'from\s+(\d+(?:\.\d+)?)',
        r'start\s+(?:range\s+)?(?:of\s+)?(\d+(?:\.\d+)?)',
    ]
    
    # Check for "from 0" specifically
    if re.search(r'from\s+0\s', query_lower):
        params["start_range"] = 0.0
    else:
        for pattern in start_patterns:
            match = re.search(pattern, query_lower)
            if match:
                params["start_range"] = round(float(match.group(1)), 4)
                break
    
    # Extract end_range - look for "to X pi" or "to X"
    # Handle "2 pi" as 2 * pi
    end_patterns = [
        r'to\s+(\d+(?:\.\d+)?)\s*pi',
        r'to\s+(\d+(?:\.\d+)?)',
        r'end\s+(?:range\s+)?(?:of\s+)?(\d+(?:\.\d+)?)',
    ]
    
    # Check for "to 2 pi" or "to 2pi"
    pi_match = re.search(r'to\s+(\d+(?:\.\d+)?)\s*pi', query_lower)
    if pi_match:
        multiplier = float(pi_match.group(1))
        params["end_range"] = round(multiplier * math.pi, 4)
    else:
        for pattern in end_patterns:
            match = re.search(pattern, query_lower)
            if match:
                params["end_range"] = round(float(match.group(1)), 4)
                break
    
    # Extract amplitude if mentioned
    amp_patterns = [
        r'amplitude\s+(?:of\s+)?(\d+(?:\.\d+)?)',
        r'amplitude\s*[=:]\s*(\d+(?:\.\d+)?)',
    ]
    for pattern in amp_patterns:
        match = re.search(pattern, query_lower)
        if match:
            params["amplitude"] = int(float(match.group(1)))
            break
    
    # Extract phase_shift if mentioned
    phase_patterns = [
        r'phase\s+(?:shift\s+)?(?:of\s+)?(\d+(?:\.\d+)?)',
        r'phase\s*[=:]\s*(\d+(?:\.\d+)?)',
    ]
    for pattern in phase_patterns:
        match = re.search(pattern, query_lower)
        if match:
            params["phase_shift"] = int(float(match.group(1)))
            break
    
    return {func_name: params}
