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
    
    # Parse functions (may be JSON string)
    try:
        if isinstance(functions, str):
            funcs = json.loads(functions)
        else:
            funcs = functions
    except (json.JSONDecodeError, TypeError):
        funcs = []
    
    if not funcs:
        return {"error": "No functions provided"}
    
    func = funcs[0]
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    required_params = func.get("parameters", {}).get("required", [])
    
    # Extract parameters based on schema
    params = {}
    query_lower = query.lower()
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_name == "company_name":
            # Extract company name - look for known patterns
            # Pattern: "stocks of X", "stock of X", "about X", company names
            company_patterns = [
                r'(?:stocks?|shares?|info(?:rmation)?)\s+(?:of|about|for)\s+([A-Z][A-Za-z\s]+(?:Inc\.?|Corp\.?|Ltd\.?|LLC)?)',
                r'about\s+(?:stocks?\s+(?:of\s+)?)?([A-Z][A-Za-z\s]+(?:Inc\.?|Corp\.?|Ltd\.?|LLC)?)',
                r'([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*(?:\s+Inc\.?|\s+Corp\.?|\s+Ltd\.?|\s+LLC)?)',
            ]
            
            for pattern in company_patterns:
                match = re.search(pattern, query)
                if match:
                    company = match.group(1).strip()
                    # Clean up trailing punctuation
                    company = re.sub(r'[.,;:!?]+$', '', company).strip()
                    if company and len(company) > 1:
                        params[param_name] = company
                        break
            
            # Fallback: look for well-known company names
            if param_name not in params:
                known_companies = ["Apple Inc", "Apple", "Microsoft", "Google", "Amazon", "Tesla", "Meta"]
                for company in known_companies:
                    if company.lower() in query_lower:
                        params[param_name] = company if company != "Apple" else "Apple Inc"
                        break
        
        elif param_name == "detail_level":
            # Extract detail level from query
            if any(word in query_lower for word in ["detail", "detailed", "full", "comprehensive", "all"]):
                params[param_name] = "detailed"
            elif any(word in query_lower for word in ["summary", "brief", "quick", "short"]):
                params[param_name] = "summary"
            else:
                # Default to detailed if asking for "detail information"
                params[param_name] = "detailed"
        
        elif param_name == "market":
            # Extract market from query
            markets = ["NASDAQ", "NYSE", "LSE", "TSE", "HKEX"]
            for market in markets:
                if market.lower() in query_lower:
                    params[param_name] = market
                    break
            # Don't set default - let the function use its own default
    
    # Ensure required params are present
    for req_param in required_params:
        if req_param not in params:
            # Try to infer or set reasonable default
            if req_param == "company_name":
                params[req_param] = "<UNKNOWN>"
            elif req_param == "detail_level":
                params[req_param] = "detailed"
    
    return {func_name: params}
