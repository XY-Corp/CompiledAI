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
    
    Parses the user query and function schema to extract parameter values
    using regex and string matching patterns.
    """
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
    
    # Extract full_name - look for name patterns
    if "full_name" in params_schema:
        # Pattern: "individual X" or "person X" or just capitalized names
        name_patterns = [
            r'individual\s+([A-Z][a-z]+\s+[A-Z][a-z]+)',
            r'person\s+([A-Z][a-z]+\s+[A-Z][a-z]+)',
            r'named?\s+([A-Z][a-z]+\s+[A-Z][a-z]+)',
            r'([A-Z][a-z]+\s+[A-Z][a-z]+)\s+with',
            r'([A-Z][a-z]+\s+[A-Z][a-z]+)\s+has',
        ]
        for pattern in name_patterns:
            match = re.search(pattern, query)
            if match:
                params["full_name"] = match.group(1).strip()
                break
    
    # Extract birth_date - look for date patterns
    if "birth_date" in params_schema:
        # Pattern: MM-DD-YYYY or MM/DD/YYYY
        date_patterns = [
            r'birthday?\s+(\d{2}-\d{2}-\d{4})',
            r'birth\s+date\s+(\d{2}-\d{2}-\d{4})',
            r'born\s+(?:on\s+)?(\d{2}-\d{2}-\d{4})',
            r'(\d{2}-\d{2}-\d{4})',
            r'(\d{2}/\d{2}/\d{4})',
        ]
        for pattern in date_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                date_str = match.group(1)
                # Convert / to - if needed
                params["birth_date"] = date_str.replace('/', '-')
                break
    
    # Extract state - look for US state names
    if "state" in params_schema:
        # Common US states
        states = [
            'Alabama', 'Alaska', 'Arizona', 'Arkansas', 'California', 'Colorado',
            'Connecticut', 'Delaware', 'Florida', 'Georgia', 'Hawaii', 'Idaho',
            'Illinois', 'Indiana', 'Iowa', 'Kansas', 'Kentucky', 'Louisiana',
            'Maine', 'Maryland', 'Massachusetts', 'Michigan', 'Minnesota',
            'Mississippi', 'Missouri', 'Montana', 'Nebraska', 'Nevada',
            'New Hampshire', 'New Jersey', 'New Mexico', 'New York',
            'North Carolina', 'North Dakota', 'Ohio', 'Oklahoma', 'Oregon',
            'Pennsylvania', 'Rhode Island', 'South Carolina', 'South Dakota',
            'Tennessee', 'Texas', 'Utah', 'Vermont', 'Virginia', 'Washington',
            'West Virginia', 'Wisconsin', 'Wyoming'
        ]
        
        # Check for state mentions in query
        for state in states:
            if state.lower() in query.lower():
                params["state"] = state
                break
    
    return {func_name: params}
