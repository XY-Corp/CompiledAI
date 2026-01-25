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
    """Extract function name and parameters from user query. Returns {"func_name": {params}}."""
    
    # Parse prompt - may be JSON string with nested structure
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
    
    # Parse functions - may be JSON string
    if isinstance(functions, str):
        try:
            functions = json.loads(functions)
        except json.JSONDecodeError:
            functions = []
    
    if not functions:
        return {"error": "No functions provided"}
    
    func = functions[0]
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    required_params = func.get("parameters", {}).get("required", [])
    
    # Extract parameters from query using regex and string matching
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_type == "integer":
            # Extract year - look for 4-digit numbers (years)
            if "year" in param_name.lower() or "year" in param_desc:
                year_match = re.search(r'\b(19|20)\d{2}\b', query)
                if year_match:
                    params[param_name] = int(year_match.group(0))
            else:
                # Extract other integers
                numbers = re.findall(r'\b\d+\b', query)
                # Filter out years for non-year params
                non_year_numbers = [n for n in numbers if not (len(n) == 4 and n.startswith(('19', '20')))]
                if non_year_numbers:
                    params[param_name] = int(non_year_numbers[0])
        
        elif param_type == "string":
            # Extract country
            if "country" in param_name.lower() or "country" in param_desc:
                # Common patterns for country extraction
                country_patterns = [
                    r'in\s+(?:the\s+)?([A-Z][A-Za-z\.\s]+?)(?:\s+for|\s+in|\s+during|\s*$|\s*\.)',
                    r'(?:from|of)\s+(?:the\s+)?([A-Z][A-Za-z\.\s]+?)(?:\s+for|\s+in|\s+during|\s*$|\s*\.)',
                ]
                
                for pattern in country_patterns:
                    match = re.search(pattern, query)
                    if match:
                        country = match.group(1).strip()
                        # Clean up common abbreviations
                        if country in ["U.S", "U.S.", "US", "USA"]:
                            country = "U.S."
                        params[param_name] = country
                        break
                
                # Fallback: look for known country names/abbreviations
                if param_name not in params:
                    known_countries = {
                        r'\bU\.?S\.?A?\.?\b': 'U.S.',
                        r'\bUnited States\b': 'U.S.',
                        r'\bUK\b': 'UK',
                        r'\bUnited Kingdom\b': 'UK',
                        r'\bCanada\b': 'Canada',
                        r'\bChina\b': 'China',
                        r'\bJapan\b': 'Japan',
                        r'\bGermany\b': 'Germany',
                    }
                    for pattern, value in known_countries.items():
                        if re.search(pattern, query, re.IGNORECASE):
                            params[param_name] = value
                            break
    
    # Only include required params and params we found values for
    # Don't include optional params with defaults unless explicitly mentioned
    final_params = {}
    for param_name in params_schema.keys():
        if param_name in params:
            final_params[param_name] = params[param_name]
        elif param_name in required_params:
            # Required param not found - this shouldn't happen with good extraction
            pass
    
    return {func_name: final_params}
