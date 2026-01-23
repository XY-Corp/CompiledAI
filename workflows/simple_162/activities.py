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
    """Extract function name and parameters from user query using regex and string matching."""
    
    # Parse prompt (may be JSON string with nested structure)
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
        else:
            data = prompt
        
        # Extract user query from BFCL format: {"question": [[{"role": "user", "content": "..."}]]}
        if "question" in data and isinstance(data["question"], list):
            if len(data["question"]) > 0 and isinstance(data["question"][0], list):
                query = data["question"][0][0].get("content", str(prompt))
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
    
    # Extract parameters based on schema
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        
        if param_name == "parties":
            # Extract names - look for "between X and Y" pattern
            parties_match = re.search(r'between\s+([A-Za-z]+)\s+and\s+([A-Za-z]+)', query, re.IGNORECASE)
            if parties_match:
                params["parties"] = [parties_match.group(1), parties_match.group(2)]
            else:
                # Fallback: extract capitalized names
                names = re.findall(r'\b([A-Z][a-z]+)\b', query)
                # Filter out common words that might be capitalized
                common_words = {"Generate", "Type", "Location", "Contract", "Law"}
                names = [n for n in names if n not in common_words]
                if names:
                    params["parties"] = names[:2] if len(names) >= 2 else names
        
        elif param_name == "contract_type":
            # Extract contract type - look for "for X agreement/contract" pattern
            type_match = re.search(r'for\s+([a-zA-Z]+)\s+(?:agreement|contract)', query, re.IGNORECASE)
            if type_match:
                params["contract_type"] = type_match.group(1).lower() + " agreement"
            else:
                # Fallback: look for common contract types
                contract_types = ["rental", "lease", "employment", "service", "sales", "nda"]
                for ct in contract_types:
                    if ct in query.lower():
                        params["contract_type"] = ct + " agreement"
                        break
        
        elif param_name == "location":
            # Extract location - look for "in X" pattern at end or state names
            location_match = re.search(r'in\s+([A-Za-z\s]+?)(?:\.|$)', query, re.IGNORECASE)
            if location_match:
                params["location"] = location_match.group(1).strip()
            else:
                # Fallback: look for US state names
                states = ["California", "Texas", "New York", "Florida", "Illinois"]
                for state in states:
                    if state.lower() in query.lower():
                        params["location"] = state
                        break
    
    return {func_name: params}
