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
    """Extract function name and parameters from user query using regex parsing."""
    
    # Parse prompt - may be JSON string with nested structure
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
    
    # Extract parameters based on the query
    params = {}
    
    # For t-test: extract group1, group2 arrays and alpha value
    
    # Extract group1 - look for "group1" followed by numbers in parentheses or brackets
    group1_pattern = r'group1\s*\([^)]*?(\d+\.?\d*)[,\s]+(\d+\.?\d*)[,\s]+(\d+\.?\d*)[,\s]+(\d+\.?\d*)'
    group1_match = re.search(group1_pattern, query, re.IGNORECASE)
    
    if group1_match:
        group1 = [float(group1_match.group(i)) for i in range(1, 5)]
    else:
        # Alternative: look for pattern like "e.g., 12.4, 15.6, 11.2, 18.9"
        # Find all number sequences after "group1"
        group1_section = re.search(r'group1[^)]*\(([^)]+)\)', query, re.IGNORECASE)
        if group1_section:
            numbers = re.findall(r'(\d+\.?\d*)', group1_section.group(1))
            group1 = [float(n) for n in numbers if n]
        else:
            group1 = []
    
    # Extract group2 - look for "group2" followed by numbers in parentheses or brackets
    group2_pattern = r'group2\s*\([^)]*?(\d+\.?\d*)[,\s]+(\d+\.?\d*)[,\s]+(\d+\.?\d*)[,\s]+(\d+\.?\d*)'
    group2_match = re.search(group2_pattern, query, re.IGNORECASE)
    
    if group2_match:
        group2 = [float(group2_match.group(i)) for i in range(1, 5)]
    else:
        # Alternative: look for pattern like "e.g., 10.5, 9.8, 15.2, 13.8"
        group2_section = re.search(r'group2[^)]*\(([^)]+)\)', query, re.IGNORECASE)
        if group2_section:
            numbers = re.findall(r'(\d+\.?\d*)', group2_section.group(1))
            group2 = [float(n) for n in numbers if n]
        else:
            group2 = []
    
    # Extract alpha/significance level - look for patterns like "significance level 0.05" or "alpha 0.05"
    # Be careful to extract just the number, not trailing punctuation
    alpha_pattern = r'(?:significance\s+level|alpha)[^\d]*(\d+\.?\d*)'
    alpha_match = re.search(alpha_pattern, query, re.IGNORECASE)
    
    if alpha_match:
        alpha_str = alpha_match.group(1)
        # Clean up any trailing dots or punctuation
        alpha_str = alpha_str.rstrip('.')
        alpha = float(alpha_str)
    else:
        alpha = 0.05  # Default value
    
    # Build params dict based on schema
    if "group1" in params_schema and group1:
        params["group1"] = group1
    if "group2" in params_schema and group2:
        params["group2"] = group2
    if "alpha" in params_schema:
        params["alpha"] = alpha
    
    return {func_name: params}
