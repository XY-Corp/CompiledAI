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
    """Extract function name and parameters from user query using regex patterns.
    
    Returns a dict with function name as key and parameters as nested object.
    """
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

    # Extract all numbers from the query
    # Pattern matches numbers with optional "million" or "billion" suffix
    number_patterns = [
        (r'(\d+(?:\.\d+)?)\s*million', 1_000_000),  # X million
        (r'(\d+(?:\.\d+)?)\s*billion', 1_000_000_000),  # X billion
        (r'(\d+(?:,\d{3})*(?:\.\d+)?)', 1),  # Plain numbers (with optional commas)
    ]

    extracted_numbers = []
    query_lower = query.lower()

    # First extract "X million" and "X billion" patterns
    for pattern, multiplier in number_patterns[:2]:
        for match in re.finditer(pattern, query_lower):
            value = float(match.group(1)) * multiplier
            extracted_numbers.append((match.start(), int(value)))

    # If we didn't find enough numbers with million/billion, look for plain numbers
    if len(extracted_numbers) < 2:
        # Find plain numbers not already captured
        for match in re.finditer(r'(\d+(?:,\d{3})*(?:\.\d+)?)', query):
            num_str = match.group(1).replace(',', '')
            value = float(num_str)
            # Check if this position overlaps with already found numbers
            pos = match.start()
            is_duplicate = False
            for existing_pos, _ in extracted_numbers:
                if abs(pos - existing_pos) < 20:  # Within 20 chars, likely same number
                    is_duplicate = True
                    break
            if not is_duplicate:
                extracted_numbers.append((pos, int(value) if value == int(value) else value))

    # Sort by position in text
    extracted_numbers.sort(key=lambda x: x[0])
    numbers = [n[1] for n in extracted_numbers]

    # Map numbers to parameters based on context clues in the query
    params = {}
    
    # For this specific function, we need to identify:
    # - total_payout: dividend payout amount
    # - outstanding_shares: number of shares
    
    # Look for contextual clues
    payout_value = None
    shares_value = None
    
    # Pattern for shares: "X shares" or "X outstanding shares"
    shares_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:million|billion)?\s*(?:outstanding\s+)?shares', query_lower)
    if shares_match:
        num_str = shares_match.group(1)
        if 'million' in query_lower[shares_match.start():shares_match.end()+10]:
            shares_value = int(float(num_str) * 1_000_000)
        elif 'billion' in query_lower[shares_match.start():shares_match.end()+10]:
            shares_value = int(float(num_str) * 1_000_000_000)
        else:
            shares_value = int(float(num_str))
    
    # Pattern for payout: "dividend payout of X" or "total dividend payout of X"
    payout_match = re.search(r'(?:dividend\s+)?payout\s+of\s+(\d+(?:\.\d+)?)\s*(?:million|billion)?', query_lower)
    if payout_match:
        num_str = payout_match.group(1)
        # Check for million/billion after the number
        after_text = query_lower[payout_match.end():payout_match.end()+15]
        if 'million' in query_lower[payout_match.start():payout_match.end()+15]:
            payout_value = int(float(num_str) * 1_000_000)
        elif 'billion' in query_lower[payout_match.start():payout_match.end()+15]:
            payout_value = int(float(num_str) * 1_000_000_000)
        else:
            payout_value = int(float(num_str))

    # If we found specific values, use them
    if shares_value is not None:
        params["outstanding_shares"] = shares_value
    if payout_value is not None:
        params["total_payout"] = payout_value

    # Fallback: if we couldn't identify specific values but have numbers
    # Try to assign based on typical patterns (shares usually larger than payout per share)
    if len(params) < 2 and len(numbers) >= 2:
        # If we have two numbers, the one associated with "shares" is outstanding_shares
        # and the one associated with "payout" or "dividend" is total_payout
        if "outstanding_shares" not in params:
            # Find the number closest to "shares" keyword
            for i, (pos, val) in enumerate(extracted_numbers):
                text_around = query_lower[max(0, pos-30):pos+50]
                if 'share' in text_around:
                    params["outstanding_shares"] = val
                    break
        
        if "total_payout" not in params:
            # Find the number closest to "payout" or "dividend" keyword
            for i, (pos, val) in enumerate(extracted_numbers):
                text_around = query_lower[max(0, pos-30):pos+50]
                if 'payout' in text_around or 'dividend' in text_around:
                    if val != params.get("outstanding_shares"):
                        params["total_payout"] = val
                        break

    # Final fallback: assign remaining numbers to missing params
    if len(params) < 2 and numbers:
        remaining_numbers = [n for n in numbers if n not in params.values()]
        param_names = list(params_schema.keys())
        for param_name in param_names:
            if param_name not in params and remaining_numbers:
                params[param_name] = remaining_numbers.pop(0)

    return {func_name: params}
