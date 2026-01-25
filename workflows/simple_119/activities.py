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
    """Extract function name and parameters from user query. Returns {func_name: {params}}."""
    
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
    props = func.get("parameters", {}).get("properties", {})
    
    params = {}
    
    # Extract arrays - look for patterns like [1,2,3] or Sample1: [1,2,3]
    # Pattern for arrays with labels
    array_patterns = [
        r'Sample1:\s*\[([^\]]+)\]',
        r'Sample2:\s*\[([^\]]+)\]',
        r'sample1:\s*\[([^\]]+)\]',
        r'sample2:\s*\[([^\]]+)\]',
    ]
    
    # Extract Sample1 array
    sample1_match = re.search(r'[Ss]ample\s*1[:\s]*\[([^\]]+)\]', query)
    if sample1_match:
        sample1_str = sample1_match.group(1)
        sample1 = [int(x.strip()) for x in sample1_str.split(',') if x.strip()]
        params["sample1"] = sample1
    
    # Extract Sample2 array
    sample2_match = re.search(r'[Ss]ample\s*2[:\s]*\[([^\]]+)\]', query)
    if sample2_match:
        sample2_str = sample2_match.group(1)
        sample2 = [int(x.strip()) for x in sample2_str.split(',') if x.strip()]
        params["sample2"] = sample2
    
    # If no labeled arrays found, try to find any two arrays
    if "sample1" not in params or "sample2" not in params:
        all_arrays = re.findall(r'\[([^\]]+)\]', query)
        if len(all_arrays) >= 2:
            if "sample1" not in params:
                params["sample1"] = [int(x.strip()) for x in all_arrays[0].split(',') if x.strip()]
            if "sample2" not in params:
                params["sample2"] = [int(x.strip()) for x in all_arrays[1].split(',') if x.strip()]
    
    # Extract significance level - look for patterns like "0.05", "significance level of 0.05"
    sig_match = re.search(r'significance\s+level\s+(?:of\s+)?(\d+\.?\d*)', query, re.IGNORECASE)
    if sig_match:
        params["significance_level"] = float(sig_match.group(1))
    else:
        # Look for standalone decimal that could be significance level (typically 0.01, 0.05, 0.1)
        decimal_match = re.search(r'(?:at|with|using)\s+(\d+\.\d+)', query, re.IGNORECASE)
        if decimal_match:
            val = float(decimal_match.group(1))
            if val <= 1.0:  # Significance levels are <= 1
                params["significance_level"] = val
    
    return {func_name: params}
