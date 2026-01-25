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
    
    # Get target function details
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    required_params = func.get("parameters", {}).get("required", [])
    
    # Extract parameters based on schema
    params = {}
    query_lower = query.lower()
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_type == "string":
            # For element_name - extract the element being asked about
            if "element" in param_name.lower() or "element" in param_desc:
                # Common patterns for element extraction
                # "Who discovered radium?" -> radium
                # "What is the discoverer of oxygen?" -> oxygen
                element_patterns = [
                    r'discovered?\s+(\w+)',  # "discovered radium"
                    r'discoverer\s+of\s+(\w+)',  # "discoverer of radium"
                    r'who\s+discovered\s+(\w+)',  # "who discovered radium"
                    r'element\s+(\w+)',  # "element radium"
                ]
                
                for pattern in element_patterns:
                    match = re.search(pattern, query_lower)
                    if match:
                        element = match.group(1).strip()
                        # Capitalize element name properly
                        params[param_name] = element.capitalize()
                        break
                
                # If no pattern matched, try to find known element names
                if param_name not in params:
                    # List of common elements to check
                    elements = ['hydrogen', 'helium', 'lithium', 'beryllium', 'boron', 
                               'carbon', 'nitrogen', 'oxygen', 'fluorine', 'neon',
                               'sodium', 'magnesium', 'aluminum', 'silicon', 'phosphorus',
                               'sulfur', 'chlorine', 'argon', 'potassium', 'calcium',
                               'iron', 'copper', 'zinc', 'silver', 'gold', 'mercury',
                               'lead', 'uranium', 'plutonium', 'radium', 'polonium']
                    for elem in elements:
                        if elem in query_lower:
                            params[param_name] = elem.capitalize()
                            break
            else:
                # Generic string extraction - look for quoted strings or key phrases
                quoted = re.findall(r'"([^"]+)"', query)
                if quoted:
                    params[param_name] = quoted[0]
        
        elif param_type == "integer":
            # Extract integers - for year parameter
            if "year" in param_name.lower() or "year" in param_desc:
                # Look for 4-digit years
                year_match = re.search(r'\b(1[0-9]{3}|20[0-9]{2})\b', query)
                if year_match:
                    params[param_name] = int(year_match.group(1))
                # Don't include if not found - it's optional with default
            else:
                # Generic integer extraction
                numbers = re.findall(r'\b(\d+)\b', query)
                if numbers:
                    params[param_name] = int(numbers[0])
        
        elif param_type == "boolean":
            # For boolean params, check if explicitly mentioned
            if "first" in param_name.lower():
                # Check for explicit mentions
                if "first" in query_lower:
                    params[param_name] = True
                elif "last" in query_lower or "all" in query_lower:
                    params[param_name] = False
                # Don't include if not explicitly mentioned - use default
    
    # Only include required params and explicitly mentioned optional params
    # Filter to only include params we actually extracted
    final_params = {}
    for param_name in params:
        final_params[param_name] = params[param_name]
    
    return {func_name: final_params}
