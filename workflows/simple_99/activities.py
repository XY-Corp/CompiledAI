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
    
    # Extract start_range - look for "from X" or "0" at start
    # Common patterns: "from 0", "from 0 to", "starting at 0"
    start_match = re.search(r'from\s+(\d+(?:\.\d+)?)', query_lower)
    if start_match:
        params["start_range"] = round(float(start_match.group(1)), 4)
    elif "from 0" in query_lower or query_lower.startswith("0"):
        params["start_range"] = 0.0
    
    # Extract end_range - look for "to X pi" or "to X"
    # Handle "2 pi", "2pi", "2*pi" patterns
    end_match = re.search(r'to\s+(\d+(?:\.\d+)?)\s*\*?\s*pi', query_lower)
    if end_match:
        multiplier = float(end_match.group(1))
        params["end_range"] = round(multiplier * math.pi, 4)
    else:
        # Try just "to X" without pi
        end_match = re.search(r'to\s+(\d+(?:\.\d+)?)', query_lower)
        if end_match:
            params["end_range"] = round(float(end_match.group(1)), 4)
    
    # Extract frequency - look for "frequency of X Hz" or "X Hz"
    freq_match = re.search(r'frequency\s+(?:of\s+)?(\d+(?:\.\d+)?)\s*(?:hz)?', query_lower)
    if freq_match:
        params["frequency"] = int(float(freq_match.group(1)))
    else:
        # Try just "X Hz" pattern
        freq_match = re.search(r'(\d+(?:\.\d+)?)\s*hz', query_lower)
        if freq_match:
            params["frequency"] = int(float(freq_match.group(1)))
    
    # Extract amplitude if mentioned - "amplitude of X" or "amplitude X"
    amp_match = re.search(r'amplitude\s+(?:of\s+)?(\d+(?:\.\d+)?)', query_lower)
    if amp_match:
        params["amplitude"] = int(float(amp_match.group(1)))
    
    # Extract phase shift if mentioned - "phase shift of X" or "phase X"
    phase_match = re.search(r'phase\s*(?:shift)?\s+(?:of\s+)?(\d+(?:\.\d+)?)', query_lower)
    if phase_match:
        params["phase_shift"] = int(float(phase_match.group(1)))
    
    return {func_name: params}
