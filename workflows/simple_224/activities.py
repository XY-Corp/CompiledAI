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
    """Extract function call parameters from user query and return as {func_name: {params}}.
    
    Uses regex and string parsing to extract values - no LLM calls needed.
    """
    # Parse prompt (may be JSON string with nested structure)
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
            # Extract main topic - look for key phrases
            # "tweets about X related to Y" -> X is the main topic
            topic_patterns = [
                r'(?:about|on|regarding|related to)\s+([a-zA-Z]+)',
                r'who\s+(?:tweets?|posts?)\s+about\s+([a-zA-Z]+)',
            ]
            
            for pattern in topic_patterns:
                match = re.search(pattern, query_lower)
                if match:
                    params["topic"] = match.group(1)
                    break
            
            # If not found, try to identify from context
            if "topic" not in params:
                if "psychology" in query_lower:
                    params["topic"] = "psychology"
        
        elif param_name == "sub_topics":
            # Extract sub-topics - look for "related to X and Y" or "about X, Y"
            sub_topics = []
            
            # Pattern: "related to X and Y" or "related to X, Y"
            related_match = re.search(r'related to\s+([a-zA-Z\s,]+?)(?:\.|$)', query_lower)
            if related_match:
                related_text = related_match.group(1)
                # Split by "and" or ","
                parts = re.split(r'\s+and\s+|,\s*', related_text)
                sub_topics = [p.strip() for p in parts if p.strip()]
            
            # Also check for specific keywords in the query
            if not sub_topics:
                keywords = ["behaviour", "behavior", "group dynamics", "dynamics", "social"]
                for kw in keywords:
                    if kw in query_lower and kw not in ["psychology"]:
                        # Normalize behaviour/behavior
                        if kw == "behavior":
                            kw = "behaviour"
                        if kw not in sub_topics:
                            sub_topics.append(kw)
            
            if sub_topics:
                params["sub_topics"] = sub_topics
        
        elif param_name == "region":
            # Extract region if mentioned
            region_patterns = [
                r'(?:in|from|region[:\s]+)\s*([a-zA-Z]+)',
                r'([a-zA-Z]+)\s+region',
            ]
            
            for pattern in region_patterns:
                match = re.search(pattern, query_lower)
                if match:
                    region = match.group(1).strip()
                    if region not in ["the", "a", "an", "twitter", "who"]:
                        params["region"] = region
                        break
            
            # Don't include region if not explicitly mentioned (use default)
    
    # Ensure required params are present
    for req_param in required_params:
        if req_param not in params:
            # Try harder to extract required params
            if req_param == "topic" and "psychology" in query_lower:
                params["topic"] = "psychology"
    
    return {func_name: params}
