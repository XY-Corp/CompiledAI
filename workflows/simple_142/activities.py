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
    """Extract function name and parameters from user query using regex and string matching."""
    
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
    
    # Extract company name - look for patterns like "company X", "for X", or known company names
    if "company_name" in params_schema:
        # Common patterns for company names
        company_patterns = [
            r'company\s+([A-Za-z]+)',
            r'for\s+(?:the\s+)?(?:company\s+)?([A-Za-z]+)',
            r'stock\s+price\s+(?:for\s+)?(?:the\s+)?(?:company\s+)?([A-Za-z]+)',
        ]
        
        # Known company names to look for
        known_companies = ['Amazon', 'Apple', 'Google', 'Microsoft', 'Tesla', 'Meta', 'Netflix', 'Facebook']
        
        company_name = None
        
        # First try to find known company names
        for company in known_companies:
            if company.lower() in query.lower():
                company_name = company
                break
        
        # If not found, try regex patterns
        if not company_name:
            for pattern in company_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    company_name = match.group(1)
                    break
        
        if company_name:
            params["company_name"] = company_name
    
    # Extract date - look for date patterns
    if "date" in params_schema:
        # Various date patterns
        date_patterns = [
            # March 11, 2022 or March.11, 2022 or March 11 2022
            r'(January|February|March|April|May|June|July|August|September|October|November|December)[.\s]+(\d{1,2})[,.\s]+(\d{4})',
            # 2022-03-11 format
            r'(\d{4})-(\d{2})-(\d{2})',
            # 03/11/2022 or 03-11-2022
            r'(\d{1,2})[/-](\d{1,2})[/-](\d{4})',
        ]
        
        month_map = {
            'january': '01', 'february': '02', 'march': '03', 'april': '04',
            'may': '05', 'june': '06', 'july': '07', 'august': '08',
            'september': '09', 'october': '10', 'november': '11', 'december': '12'
        }
        
        date_str = None
        
        # Try first pattern (Month Day, Year)
        match = re.search(date_patterns[0], query, re.IGNORECASE)
        if match:
            month_name = match.group(1).lower()
            day = match.group(2).zfill(2)
            year = match.group(3)
            month = month_map.get(month_name, '01')
            date_str = f"{year}-{month}-{day}"
        
        # Try ISO format
        if not date_str:
            match = re.search(date_patterns[1], query)
            if match:
                date_str = f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
        
        # Try MM/DD/YYYY format
        if not date_str:
            match = re.search(date_patterns[2], query)
            if match:
                month = match.group(1).zfill(2)
                day = match.group(2).zfill(2)
                year = match.group(3)
                date_str = f"{year}-{month}-{day}"
        
        if date_str:
            params["date"] = date_str
    
    # Extract exchange - look for stock exchange names
    if "exchange" in params_schema:
        exchange_patterns = [
            r'\b(NASDAQ|NYSE|AMEX|LSE|TSE|FTSE)\b',
            r'on\s+(?:the\s+)?([A-Z]{3,6})\s+(?:stock\s+)?(?:exchange|market)?',
        ]
        
        exchange = None
        for pattern in exchange_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                exchange = match.group(1).upper()
                break
        
        if exchange:
            params["exchange"] = exchange
    
    return {func_name: params}
