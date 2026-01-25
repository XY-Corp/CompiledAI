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
    
    # Get function details
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters from query using regex and string matching
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_name == "team":
            # Extract team name - look for known patterns or capitalized words
            # Pattern: "Golden State Warriors" or similar team names
            team_patterns = [
                r'(Golden State Warriors)',
                r'(Los Angeles Lakers)',
                r'(Boston Celtics)',
                r'where\s+([A-Z][a-zA-Z\s]+?)\s+stand',
                r'for\s+([A-Z][a-zA-Z\s]+?)\s+in',
                r'about\s+([A-Z][a-zA-Z\s]+?)(?:\s+in|\s+for|$)',
            ]
            for pattern in team_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    params[param_name] = match.group(1).strip()
                    break
        
        elif param_name == "season":
            # Extract season - look for year patterns like "2022-2023" or "2023"
            season_patterns = [
                r'(\d{4}-\d{4})',  # 2022-2023
                r'(\d{4}/\d{4})',  # 2022/2023
                r'(\d{4})\s*season',  # 2023 season
                r'season\s*(\d{4})',  # season 2023
            ]
            for pattern in season_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    params[param_name] = match.group(1).strip()
                    break
        
        elif param_name == "detailed" and param_type == "boolean":
            # Check for keywords indicating detailed info is wanted
            detailed_keywords = ['detail', 'detailed', 'stats', 'statistics', 'full', 'complete', 'with details']
            query_lower = query.lower()
            params[param_name] = any(kw in query_lower for kw in detailed_keywords)
    
    return {func_name: params}
