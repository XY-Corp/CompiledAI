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
    """Extract function call parameters from user query using regex and string matching."""
    
    # Parse prompt - may be JSON string with nested structure
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
            # Handle BFCL format: {"question": [[{"role": "user", "content": "..."}]]}
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
    
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    props = func.get("parameters", {}).get("properties", {})
    
    params = {}
    
    # Extract initial_investment - look for "started with $X" or "initial investment of $X"
    initial_match = re.search(r'started with \$?([\d,]+)', query, re.IGNORECASE)
    if not initial_match:
        initial_match = re.search(r'initial(?:ly)?\s+(?:investment\s+)?(?:of\s+)?\$?([\d,]+)', query, re.IGNORECASE)
    if initial_match:
        params["initial_investment"] = int(initial_match.group(1).replace(",", ""))
    
    # Extract annual_contribution - look for "adding $X every year" or "annual contribution of $X"
    contrib_match = re.search(r'adding \$?([\d,]+)\s+(?:to it\s+)?every year', query, re.IGNORECASE)
    if not contrib_match:
        contrib_match = re.search(r'annual(?:ly)?\s+(?:contribution\s+)?(?:of\s+)?\$?([\d,]+)', query, re.IGNORECASE)
    if contrib_match:
        params["annual_contribution"] = int(contrib_match.group(1).replace(",", ""))
    
    # Extract years - look for "X years" or "been X years"
    years_match = re.search(r'(?:been\s+)?(\d+)\s+years?', query, re.IGNORECASE)
    if not years_match:
        years_match = re.search(r'for\s+(\d+)\s+years?', query, re.IGNORECASE)
    if years_match:
        params["years"] = int(years_match.group(1))
    
    # Extract annual_return - look for "X% annual interest rate" or "annual return of X%"
    return_match = re.search(r'(?:annual\s+)?(?:interest\s+)?rate\s+of\s+(\d+(?:\.\d+)?)\s*%', query, re.IGNORECASE)
    if not return_match:
        return_match = re.search(r'(\d+(?:\.\d+)?)\s*%\s+(?:annual\s+)?(?:interest|return)', query, re.IGNORECASE)
    if not return_match:
        return_match = re.search(r'growing at (?:an )?(?:annual )?(?:interest )?rate of (\d+(?:\.\d+)?)\s*%', query, re.IGNORECASE)
    if return_match:
        params["annual_return"] = float(return_match.group(1)) / 100.0
    
    # Extract inflation_rate - look for list of percentages like "1%, 2%, 3%, 4%, and 4%"
    # Pattern for "X%, Y%, Z%, A%, and B%" or similar
    inflation_match = re.search(r'(?:inflation\s+)?rates?\s+(?:have\s+been\s+)?(?:are\s+)?([\d%,\s]+(?:and\s+[\d%\s]+)?)\s*(?:respectively|for each)', query, re.IGNORECASE)
    if inflation_match:
        inflation_str = inflation_match.group(1)
        # Extract all percentages from the matched string
        percentages = re.findall(r'(\d+(?:\.\d+)?)\s*%', inflation_str)
        if percentages:
            params["inflation_rate"] = [float(p) / 100.0 for p in percentages]
    
    # If no inflation rates found with the above pattern, try a more general approach
    if "inflation_rate" not in params:
        # Look for a sequence of percentages after "inflation"
        inflation_section = re.search(r'inflation.*?(\d+%.*?(?:\d+%[,\s]*)+)', query, re.IGNORECASE)
        if inflation_section:
            percentages = re.findall(r'(\d+(?:\.\d+)?)\s*%', inflation_section.group(1))
            if percentages:
                params["inflation_rate"] = [float(p) / 100.0 for p in percentages]
    
    # Check if adjust_for_inflation should be set - look for "taking inflation into account"
    if re.search(r'(?:taking|accounting for|adjust(?:ing)?(?:\s+for)?)\s+inflation', query, re.IGNORECASE):
        params["adjust_for_inflation"] = True
    
    return {func_name: params}
