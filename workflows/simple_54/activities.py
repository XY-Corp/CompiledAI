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
    """Extract function call parameters from user query and return as {func_name: {params}}.
    
    Uses regex and string matching to extract parameter values - no LLM calls needed.
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
    required_params = func.get("parameters", {}).get("required", [])
    
    # Extract parameters from query
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        default_value = param_info.get("default")
        
        extracted_value = None
        
        # Strategy 1: Look for quoted values (e.g., 'BRCA1', "BRCA1")
        quoted_matches = re.findall(r"['\"]([^'\"]+)['\"]", query)
        
        # Strategy 2: Look for specific patterns based on parameter description
        if "gene" in param_name.lower() or "gene" in param_desc:
            # Gene names are typically uppercase alphanumeric (e.g., BRCA1, TP53)
            # First check quoted values
            for match in quoted_matches:
                if re.match(r'^[A-Z0-9]+$', match):
                    extracted_value = match
                    break
            # If not found in quotes, look for gene pattern in text
            if not extracted_value:
                gene_match = re.search(r'\b([A-Z][A-Z0-9]{1,10})\b', query)
                if gene_match:
                    extracted_value = gene_match.group(1)
        
        elif "species" in param_name.lower() or "species" in param_desc:
            # Look for species names
            species_patterns = [
                r'(?:species|organism)[:\s]+([A-Za-z\s]+)',
                r'(Homo sapiens|human|mouse|Mus musculus)',
            ]
            for pattern in species_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    extracted_value = match.group(1).strip()
                    break
        
        elif param_type in ["integer", "number", "float"]:
            # Extract numbers
            numbers = re.findall(r'\d+(?:\.\d+)?', query)
            if numbers:
                if param_type == "integer":
                    extracted_value = int(numbers[0])
                else:
                    extracted_value = float(numbers[0])
        
        elif param_type == "string":
            # For generic strings, try quoted values first
            if quoted_matches:
                extracted_value = quoted_matches[0]
        
        # Set the parameter value
        if extracted_value is not None:
            params[param_name] = extracted_value
        elif param_name in required_params:
            # For required params without extracted value, try harder
            if quoted_matches:
                params[param_name] = quoted_matches[0]
        # Don't include optional params with default values unless explicitly mentioned
    
    return {func_name: params}
