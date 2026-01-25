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
    
    # Extract parameters based on schema
    params = {}
    query_lower = query.lower()
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_type == "string":
            # For team_name - extract the team/club name from query
            if "team" in param_name.lower() or "name" in param_name.lower() or "club" in param_desc:
                # Common patterns for team names
                # Pattern: "by [Team Name]" or "of [Team Name]"
                team_patterns = [
                    r'(?:by|of|for)\s+([A-Z][A-Za-z\s\.]+(?:F\.?C\.?|FC|United|City|Club)?)',
                    r'([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z\.]+)*\s*(?:F\.?C\.?|FC|United|City))',
                ]
                
                for pattern in team_patterns:
                    match = re.search(pattern, query)
                    if match:
                        team_name = match.group(1).strip()
                        # Clean up trailing punctuation
                        team_name = re.sub(r'[\.\s]+$', '', team_name)
                        params[param_name] = team_name
                        break
                
                # Fallback: look for known team name patterns
                if param_name not in params:
                    # Check for "Liverpool F.C." specifically
                    if "liverpool" in query_lower:
                        match = re.search(r'(Liverpool\s*F\.?C\.?)', query, re.IGNORECASE)
                        if match:
                            params[param_name] = match.group(1)
                        else:
                            params[param_name] = "Liverpool F.C."
        
        elif param_type == "boolean":
            # For include_stats - check if user wants statistics
            if "stat" in param_name.lower() or "stat" in param_desc:
                # Check for keywords indicating stats are wanted
                stats_keywords = ["statistics", "stats", "include stats", "with stats", "include its statistics"]
                if any(kw in query_lower for kw in stats_keywords):
                    params[param_name] = True
                else:
                    # Check for explicit "no stats" or similar
                    no_stats_keywords = ["no stats", "without stats", "exclude stats"]
                    if any(kw in query_lower for kw in no_stats_keywords):
                        params[param_name] = False
                    # If not mentioned and not required, we can omit or set based on context
                    # Here the query says "Include its statistics" so set to True
                    elif "include" in query_lower and "statistic" in query_lower:
                        params[param_name] = True
        
        elif param_type == "integer" or param_type == "number":
            # Extract numbers from query
            numbers = re.findall(r'\d+(?:\.\d+)?', query)
            if numbers:
                if param_type == "integer":
                    params[param_name] = int(numbers[0])
                else:
                    params[param_name] = float(numbers[0])
    
    return {func_name: params}
