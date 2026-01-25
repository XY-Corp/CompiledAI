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
    """Extract function call parameters from natural language query.
    
    Parses the user query to extract parameters for paint calculation,
    including wall dimensions, paint coverage, and exclusion areas.
    """
    # Parse prompt (may be JSON string with nested structure)
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
        else:
            data = prompt
        
        # Extract user query from BFCL format
        if "question" in data and isinstance(data["question"], list):
            if len(data["question"]) > 0 and isinstance(data["question"][0], list):
                query = data["question"][0][0].get("content", str(prompt))
            else:
                query = str(prompt)
        else:
            query = str(prompt)
    except (json.JSONDecodeError, TypeError):
        query = str(prompt)
    
    # Parse functions (may be JSON string)
    try:
        if isinstance(functions, str):
            funcs = json.loads(functions)
        else:
            funcs = functions
    except (json.JSONDecodeError, TypeError):
        funcs = []
    
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "paint_requirement.calculate")
    
    # Extract dimensions using regex
    # Look for width pattern: "width of Xft" or "X ft wide" or "Xft width"
    width_patterns = [
        r'width\s+of\s+(\d+)\s*(?:ft|feet)?',
        r'(\d+)\s*(?:ft|feet)?\s+wide',
        r'(\d+)\s*(?:ft|feet)?\s+width',
        r'width\s*[:=]?\s*(\d+)',
    ]
    
    width = None
    for pattern in width_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            width = int(match.group(1))
            break
    
    # Look for height pattern: "height of Xft" or "X ft tall/high" or "Xft height"
    height_patterns = [
        r'height\s+of\s+(\d+)\s*(?:ft|feet)?',
        r'(\d+)\s*(?:ft|feet)?\s+(?:tall|high)',
        r'(\d+)\s*(?:ft|feet)?\s+height',
        r'height\s*[:=]?\s*(\d+)',
    ]
    
    height = None
    for pattern in height_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            height = int(match.group(1))
            break
    
    # Extract paint coverage: "X sq.ft" or "X square feet" coverage
    coverage_patterns = [
        r'covers?\s+(?:approximately\s+)?(\d+)\s*(?:sq\.?\s*ft|square\s*feet)',
        r'(\d+)\s*(?:sq\.?\s*ft|square\s*feet)\s+(?:per\s+gallon|coverage)',
        r'coverage\s+(?:of\s+)?(\d+)',
    ]
    
    paint_coverage = 350  # default
    for pattern in coverage_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            paint_coverage = int(match.group(1))
            break
    
    # Extract exclusion (window, door, etc.)
    exclusion = None
    
    # Look for exclusion type and area
    exclusion_patterns = [
        r'(window|door)\s+area\s+of\s+(\d+)\s*(?:sq\.?\s*ft|square\s*feet)?',
        r'(\d+)\s*(?:sq\.?\s*ft|square\s*feet)?\s+(window|door)',
        r'exclude\s+(?:a\s+)?(window|door)\s+(?:of\s+)?(\d+)',
        r"don'?t\s+include\s+(window|door)\s+area\s+of\s+(\d+)",
    ]
    
    for pattern in exclusion_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            groups = match.groups()
            # Determine which group is type and which is area
            if groups[0].isdigit() if isinstance(groups[0], str) and groups[0].isdigit() else False:
                exclusion_area = int(groups[0])
                exclusion_type = groups[1].lower()
            else:
                exclusion_type = groups[0].lower()
                exclusion_area = int(groups[1])
            
            exclusion = {
                "type": exclusion_type,
                "area": exclusion_area
            }
            break
    
    # Build result with exact parameter structure from schema
    params = {
        "area": {
            "width": width if width else 0,
            "height": height if height else 0
        },
        "paint_coverage": paint_coverage
    }
    
    # Only include exclusion if found
    if exclusion:
        params["exclusion"] = exclusion
    
    return {func_name: params}
