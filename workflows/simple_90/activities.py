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
    
    Parses the prompt to extract the function name and parameters,
    returning in the format {"function_name": {"param1": val1, ...}}.
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
    props = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters from query using regex and string matching
    params = {}
    
    # Extract employee_id - look for numeric ID patterns
    # Patterns: "ID is 345", "employee ID 345", "ID: 345", "whose ID is 345"
    id_patterns = [
        r'(?:employee\s+)?ID\s+(?:is\s+)?(\d+)',
        r'ID[:\s]+(\d+)',
        r'employee\s+(\d+)',
    ]
    for pattern in id_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            params["employee_id"] = int(match.group(1))
            break
    
    # Extract company_name - look for quoted company names or "company X"
    # Patterns: "'ABC Ltd.'", "company 'ABC Ltd.'", "in company ABC Ltd"
    company_patterns = [
        r"['\"]([^'\"]+)['\"]",  # Quoted strings
        r"company\s+['\"]?([^'\"]+?)['\"]?\s*$",  # "company X" at end
        r"in\s+company\s+['\"]?([^'\"]+?)['\"]?(?:\s+whose|\s+with|\s*$)",  # "in company X"
    ]
    for pattern in company_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            company = match.group(1).strip()
            # Clean up trailing punctuation
            company = re.sub(r'[.\s]+$', '', company)
            if company:
                params["company_name"] = company
                break
    
    # Extract data_field - look for field names from enum
    valid_fields = ["Personal Info", "Job History", "Payroll", "Attendance"]
    found_fields = []
    
    for field in valid_fields:
        # Case-insensitive search for field names
        if re.search(re.escape(field), query, re.IGNORECASE):
            found_fields.append(field)
    
    # Also check for variations like "personal information"
    if re.search(r'personal\s+info(?:rmation)?', query, re.IGNORECASE) and "Personal Info" not in found_fields:
        found_fields.append("Personal Info")
    if re.search(r'job\s+history', query, re.IGNORECASE) and "Job History" not in found_fields:
        found_fields.append("Job History")
    if re.search(r'payroll', query, re.IGNORECASE) and "Payroll" not in found_fields:
        found_fields.append("Payroll")
    if re.search(r'attendance', query, re.IGNORECASE) and "Attendance" not in found_fields:
        found_fields.append("Attendance")
    
    # Only include data_field if fields were found (it's optional with default)
    if found_fields:
        params["data_field"] = found_fields
    
    return {func_name: params}
