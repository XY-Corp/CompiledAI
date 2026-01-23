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
    """Extract function call parameters from natural language query using regex.
    
    Returns format: {"function_name": {"param1": val1, "param2": val2}}
    """
    # Parse prompt - may be JSON string
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
            # Extract user query from BFCL format
            if "question" in data and isinstance(data["question"], list):
                if len(data["question"]) > 0 and isinstance(data["question"][0], list):
                    query = data["question"][0][0].get("content", str(prompt))
                else:
                    query = str(prompt)
            else:
                query = str(prompt)
        else:
            query = str(prompt)
    except (json.JSONDecodeError, TypeError):
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
    func_name = func.get("name", "unknown")
    
    # For calculate_fitness: extract trait values and contributions
    # Query: "trait A contributing to 40% ... trait B contributing 60%, if trait A has a value of 0.8 and trait B a value of 0.7"
    
    # Extract trait values (decimal numbers like 0.8, 0.7)
    # Pattern: "value of X.X" or "a value of X.X"
    value_pattern = r'(?:has\s+)?(?:a\s+)?value\s+of\s+(\d+\.?\d*)'
    value_matches = re.findall(value_pattern, query, re.IGNORECASE)
    
    # Extract contributions (percentages like 40%, 60%)
    # Pattern: "contributing to X%" or "contributing X%"
    contribution_pattern = r'contribut(?:ing|es?)\s+(?:to\s+)?(\d+)%'
    contribution_matches = re.findall(contribution_pattern, query, re.IGNORECASE)
    
    # Convert to proper types
    trait_values = []
    for v in value_matches:
        # Clean the value - remove trailing punctuation
        clean_v = v.rstrip('.')
        try:
            trait_values.append(float(clean_v))
        except ValueError:
            pass
    
    trait_contributions = []
    for c in contribution_matches:
        # Clean the contribution - remove trailing punctuation
        clean_c = c.rstrip('.')
        try:
            # Convert percentage to decimal (40% -> 0.4)
            trait_contributions.append(float(clean_c) / 100.0)
        except ValueError:
            pass
    
    # Build result with exact parameter names from schema
    result = {
        func_name: {
            "trait_values": trait_values,
            "trait_contributions": trait_contributions
        }
    }
    
    return result
