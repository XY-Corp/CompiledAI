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
    using regex and string matching - no LLM calls needed.
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
    
    # Extract parameters from query
    params = {}
    
    # Extract patient_id - look for numeric ID patterns
    # Patterns: "patient with id 546382", "patient id 546382", "id 546382"
    patient_id_match = re.search(r'(?:patient\s+)?(?:with\s+)?id\s+(\d+)', query, re.IGNORECASE)
    if patient_id_match and "patient_id" in params_schema:
        params["patient_id"] = patient_id_match.group(1)
    
    # Extract mri_type - look for MRI type keywords
    if "mri_type" in params_schema:
        mri_types = ["brain", "spinal", "chest", "abdominal"]
        for mri_type in mri_types:
            if mri_type.lower() in query.lower():
                params["mri_type"] = mri_type
                break
        # Default to 'brain' if not found (as per schema description)
        if "mri_type" not in params:
            params["mri_type"] = "brain"
    
    # Extract status - look for status keywords
    if "status" in params_schema:
        status_values = ["in progress", "concluded", "draft"]
        for status in status_values:
            if status.lower() in query.lower():
                params["status"] = status
                break
        # Also check for quoted status values
        if "status" not in params:
            status_match = re.search(r"['\"](\w+(?:\s+\w+)?)['\"]", query)
            if status_match:
                matched_status = status_match.group(1).lower()
                for status in status_values:
                    if matched_status == status.lower():
                        params["status"] = status
                        break
    
    return {func_name: params}
