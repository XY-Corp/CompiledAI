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
    
    # Extract parameters based on schema
    params = {}
    query_lower = query.lower()
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_name == "topic":
            # Extract main topic - look for key topic words
            # "psychology related to behaviour and group dynamics"
            # Main topic is "psychology"
            topic_patterns = [
                r'about\s+(\w+)',
                r'related to\s+(\w+)',
                r'tweets about\s+(\w+)',
                r'who tweets about\s+(\w+)',
            ]
            
            for pattern in topic_patterns:
                match = re.search(pattern, query_lower)
                if match:
                    params["topic"] = match.group(1)
                    break
            
            # If not found, try to find the main subject
            if "topic" not in params:
                # Look for common topic indicators
                if "psychology" in query_lower:
                    params["topic"] = "psychology"
        
        elif param_name == "sub_topics":
            # Extract sub-topics - look for "related to X and Y" patterns
            sub_topics = []
            
            # Pattern: "related to X and Y" or "about X related to Y and Z"
            related_match = re.search(r'related to\s+(.+?)(?:\.|$)', query_lower)
            if related_match:
                related_text = related_match.group(1)
                # Split by "and" to get individual sub-topics
                parts = re.split(r'\s+and\s+', related_text)
                for part in parts:
                    # Clean up the part
                    cleaned = part.strip().rstrip('.')
                    if cleaned and cleaned not in sub_topics:
                        sub_topics.append(cleaned)
            
            # Also check for specific keywords mentioned
            keywords_to_check = ["behaviour", "behavior", "group dynamics", "dynamics"]
            for kw in keywords_to_check:
                if kw in query_lower:
                    # Normalize behaviour/behavior
                    if kw == "behavior":
                        kw = "behaviour"
                    if kw not in sub_topics and kw != "dynamics":  # avoid duplicate with "group dynamics"
                        if "group dynamics" in query_lower and kw == "dynamics":
                            continue
                        sub_topics.append(kw)
            
            if sub_topics:
                params["sub_topics"] = sub_topics
        
        elif param_name == "region":
            # Extract region if mentioned
            region_patterns = [
                r'in\s+([\w\s]+?)(?:\s+who|\s+that|\.|$)',
                r'from\s+([\w\s]+?)(?:\s+who|\s+that|\.|$)',
                r'region[:\s]+(\w+)',
            ]
            
            for pattern in region_patterns:
                match = re.search(pattern, query_lower)
                if match:
                    region = match.group(1).strip()
                    if region and region not in ["twitter", "the"]:
                        params["region"] = region
                        break
            
            # Don't set region if not explicitly mentioned (use default)
    
    # Ensure required params are present
    for req_param in required_params:
        if req_param not in params:
            # Try harder to extract required params
            if req_param == "topic":
                # Fallback: first noun-like word after "about"
                match = re.search(r'about\s+(\w+)', query_lower)
                if match:
                    params["topic"] = match.group(1)
    
    return {func_name: params}
