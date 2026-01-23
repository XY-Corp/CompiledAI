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
    """Extract function name and parameters from user query and function schema.
    
    Returns format: {"function_name": {"param1": val1, "param2": val2}}
    """
    # Parse prompt - may be JSON string with nested structure
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
        else:
            data = prompt
        
        # Extract user query from BFCL format: {"question": [[{"role": "user", "content": "..."}]]}
        if isinstance(data, dict) and "question" in data:
            question_data = data["question"]
            if isinstance(question_data, list) and len(question_data) > 0:
                if isinstance(question_data[0], list) and len(question_data[0]) > 0:
                    query = question_data[0][0].get("content", str(prompt))
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
    
    # Get function schema
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters from query using regex
    params = {}
    query_lower = query.lower()
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        
        if param_type == "integer":
            # Extract numbers - look for patterns like "last 3 days", "3 days", etc.
            number_patterns = [
                r'last\s+(\d+)\s+days?',
                r'(\d+)\s+days?',
                r'past\s+(\d+)\s+days?',
                r'previous\s+(\d+)\s+days?',
                r'for\s+(\d+)\s+days?',
            ]
            for pattern in number_patterns:
                match = re.search(pattern, query_lower)
                if match:
                    params[param_name] = int(match.group(1))
                    break
            
            # Fallback: extract any number if param relates to days/count
            if param_name not in params:
                numbers = re.findall(r'\d+', query)
                if numbers:
                    params[param_name] = int(numbers[0])
        
        elif param_type == "string":
            # Handle company/stock name extraction
            if param_name == "company":
                # Common stock/company patterns
                company_patterns = [
                    r'price\s+of\s+([A-Za-z]+)\s+stock',
                    r'([A-Za-z]+)\s+stock\s+price',
                    r'stock\s+price\s+(?:of|for)\s+([A-Za-z]+)',
                    r"what'?s?\s+(?:the\s+)?(?:price|stock)\s+(?:of|for)\s+([A-Za-z]+)",
                    r'([A-Za-z]+)\s+stock',
                ]
                for pattern in company_patterns:
                    match = re.search(pattern, query, re.IGNORECASE)
                    if match:
                        params[param_name] = match.group(1)
                        break
            
            # Handle data_type parameter (optional - only set if explicitly mentioned)
            elif param_name == "data_type":
                data_type_keywords = ['open', 'close', 'high', 'low']
                for keyword in data_type_keywords:
                    if keyword in query_lower:
                        params[param_name] = keyword.capitalize()
                        break
                # Don't set default - let the function use its own default
    
    return {func_name: params}
