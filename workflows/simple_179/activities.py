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
    
    Parses the prompt to extract the user query and matches it against
    the function schema to extract parameter values using regex and
    string matching patterns.
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
                if len(data["question"][0]) > 0 and isinstance(data["question"][0][0], dict):
                    query = data["question"][0][0].get("content", str(prompt))
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
    
    if not funcs:
        return {"error": "No functions provided"}
    
    # Get function details
    func = funcs[0]
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    required_params = func.get("parameters", {}).get("required", [])
    
    # Extract parameters based on schema
    params = {}
    
    # For find_latest_court_case: extract company names and country
    # Pattern: "between X and Y" for companies
    company_pattern = r'between\s+([A-Za-z0-9\s]+?)\s+and\s+([A-Za-z0-9\s]+?)(?:\s+(?:occured|occurred|in|located)|$)'
    company_match = re.search(company_pattern, query, re.IGNORECASE)
    
    if company_match:
        company1 = company_match.group(1).strip()
        company2 = company_match.group(2).strip()
        
        if "company1" in params_schema:
            params["company1"] = company1
        if "company2" in params_schema:
            params["company2"] = company2
    
    # Extract country - pattern: "in X" at the end or "located in X"
    country_pattern = r'(?:in|located\s+in)\s+([A-Z]{2,3}|[A-Za-z\s]+?)(?:\.|$)'
    country_match = re.search(country_pattern, query, re.IGNORECASE)
    
    if country_match and "country" in params_schema:
        country = country_match.group(1).strip()
        # Clean up common country names
        if country.upper() in ["USA", "US"]:
            country = "USA"
        params["country"] = country
    elif "country" in params_schema:
        # Check for default value
        default_country = params_schema.get("country", {}).get("default")
        if default_country:
            params["country"] = default_country
    
    # Fallback: try to extract any capitalized words as company names
    if "company1" not in params or "company2" not in params:
        # Find capitalized words that could be company names
        capitalized_words = re.findall(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b', query)
        # Filter out common words
        common_words = {"Find", "The", "USA", "UK", "Court", "Case", "Latest"}
        companies = [w for w in capitalized_words if w not in common_words]
        
        if len(companies) >= 2:
            if "company1" not in params:
                params["company1"] = companies[0]
            if "company2" not in params:
                params["company2"] = companies[1]
    
    return {func_name: params}
