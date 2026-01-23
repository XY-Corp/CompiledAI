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
    """Extract function name and parameters from user query based on function schema.
    
    Returns format: {"function_name": {"param1": val1, "param2": val2}}
    """
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
    
    # Extract parameters based on schema
    params = {}
    query_lower = query.lower()
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        # Extract company_name - look for company names in the query
        if param_name == "company_name" or "company" in param_name.lower():
            # Common patterns for company names
            # Look for "of X" or "about X" patterns
            company_patterns = [
                r'(?:about|of|for)\s+(?:stocks?\s+of\s+)?([A-Z][A-Za-z\s]+(?:Inc\.?|Corp\.?|LLC|Ltd\.?)?)',
                r'(?:about|of|for)\s+([A-Z][A-Za-z\s]+)',
                r'stocks?\s+of\s+([A-Z][A-Za-z\s]+(?:Inc\.?|Corp\.?|LLC|Ltd\.?)?)',
            ]
            
            for pattern in company_patterns:
                match = re.search(pattern, query)
                if match:
                    company = match.group(1).strip()
                    # Clean up trailing punctuation
                    company = re.sub(r'[.,;:!?]+$', '', company).strip()
                    params[param_name] = company
                    break
        
        # Extract detail_level - look for keywords like "detail", "summary", "detailed"
        elif param_name == "detail_level" or "detail" in param_name.lower():
            if "summary" in query_lower:
                params[param_name] = "summary"
            elif "detail" in query_lower:
                params[param_name] = "detailed"
            elif param_name in required_params:
                # Default to "detailed" if user asks for "detail information"
                if "detail" in query_lower or "information" in query_lower:
                    params[param_name] = "detailed"
                else:
                    params[param_name] = "summary"
        
        # Extract market - look for stock market names
        elif param_name == "market" or "market" in param_name.lower():
            market_patterns = [
                r'\b(NASDAQ|NYSE|AMEX|LSE|TSE|HKEX)\b',
                r'(?:on|in|from)\s+(?:the\s+)?([A-Z]{3,5})\s+(?:market|exchange|stock)',
            ]
            
            for pattern in market_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    params[param_name] = match.group(1).upper()
                    break
            # Note: market is optional with default 'NASDAQ', so we don't set it if not found
        
        # Generic string extraction for other parameters
        elif param_type == "string":
            # Try to extract based on parameter name patterns
            pattern = rf'{param_name}[:\s]+["\']?([^"\']+)["\']?'
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                params[param_name] = match.group(1).strip()
        
        # Extract numbers for integer/number types
        elif param_type in ["integer", "number", "float"]:
            numbers = re.findall(r'\d+(?:\.\d+)?', query)
            if numbers:
                if param_type == "integer":
                    params[param_name] = int(numbers[0])
                else:
                    params[param_name] = float(numbers[0])
    
    return {func_name: params}
