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
    """Extract function call parameters from user query and return as {func_name: {params}}."""
    
    # Parse prompt (may be JSON string with nested structure)
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
    
    # Parse functions (may be JSON string)
    try:
        if isinstance(functions, str):
            funcs = json.loads(functions)
        else:
            funcs = functions
    except (json.JSONDecodeError, TypeError):
        funcs = []
    
    # Get function schema
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters using regex and string matching
    params = {}
    query_lower = query.lower()
    
    for param_name, param_info in params_schema.items():
        param_desc = param_info.get("description", "").lower()
        
        if param_name == "entity":
            # Extract entity - look for company/organization names
            # Common patterns: "against X", "involving X", "filed against X"
            entity_patterns = [
                r'(?:against|involving|for|about)\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*)',
                r'lawsuits?\s+(?:filed\s+)?(?:against|involving)\s+([A-Z][A-Za-z]+)',
            ]
            for pattern in entity_patterns:
                match = re.search(pattern, query)
                if match:
                    params[param_name] = match.group(1).strip()
                    break
        
        elif param_name == "county":
            # Extract county - look for "X County" pattern
            county_patterns = [
                r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+[Cc]ounty',
                r'in\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+[Cc]ounty',
            ]
            for pattern in county_patterns:
                match = re.search(pattern, query)
                if match:
                    params[param_name] = match.group(1).strip()
                    break
        
        elif param_name == "state":
            # Extract state - look for state names or abbreviations
            state_patterns = [
                r'\b(California|Texas|New York|Florida|Illinois|Pennsylvania|Ohio|Georgia|North Carolina|Michigan|Arizona|Washington|Colorado|Massachusetts|Virginia|New Jersey|Tennessee|Indiana|Missouri|Maryland|Wisconsin|Minnesota|South Carolina|Alabama|Louisiana|Kentucky|Oregon|Oklahoma|Connecticut|Iowa|Utah|Nevada|Arkansas|Mississippi|Kansas|New Mexico|Nebraska|West Virginia|Idaho|Hawaii|Maine|New Hampshire|Rhode Island|Montana|Delaware|South Dakota|North Dakota|Alaska|Vermont|Wyoming)\b',
                r'\b(CA|TX|NY|FL|IL|PA|OH|GA|NC|MI|AZ|WA|CO|MA|VA|NJ|TN|IN|MO|MD|WI|MN|SC|AL|LA|KY|OR|OK|CT|IA|UT|NV|AR|MS|KS|NM|NE|WV|ID|HI|ME|NH|RI|MT|DE|SD|ND|AK|VT|WY)\b',
            ]
            for pattern in state_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    params[param_name] = match.group(1)
                    break
            
            # If no state found but it has a default, don't include it (let the function use its default)
            # Only include if explicitly mentioned
    
    return {func_name: params}
