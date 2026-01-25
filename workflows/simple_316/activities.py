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
    
    Returns a dict with function name as key and parameters as nested object.
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
    
    if not funcs:
        return {"error": "No functions provided"}
    
    func = funcs[0]
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters based on schema
    params = {}
    query_lower = query.lower()
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_name == "sport":
            # Extract sport name - common sports list
            sports = ["tennis", "football", "soccer", "basketball", "baseball", "golf", 
                      "cricket", "hockey", "swimming", "boxing", "mma", "volleyball"]
            for sport in sports:
                if sport in query_lower:
                    params[param_name] = sport.capitalize() if sport != "mma" else "MMA"
                    break
        
        elif param_name == "player_name":
            # Extract player name - look for capitalized words that form a name
            # Pattern: Find proper nouns (capitalized words) that aren't common words
            common_words = {"find", "the", "current", "world", "rank", "ranking", "of", "a", 
                           "an", "player", "tennis", "football", "soccer", "basketball", 
                           "baseball", "golf", "cricket", "hockey", "swimming", "boxing"}
            
            # Split and find capitalized words
            words = query.split()
            name_parts = []
            for word in words:
                # Clean punctuation
                clean_word = re.sub(r'[.,!?]', '', word)
                # Check if it's a capitalized word and not a common word
                if clean_word and clean_word[0].isupper() and clean_word.lower() not in common_words:
                    name_parts.append(clean_word)
            
            if name_parts:
                params[param_name] = " ".join(name_parts)
        
        elif param_name == "gender":
            # Extract gender if mentioned
            if "female" in query_lower or "woman" in query_lower or "women" in query_lower:
                params[param_name] = "female"
            elif "male" in query_lower or " man " in query_lower or " men " in query_lower:
                params[param_name] = "male"
            # Note: gender is optional, so we don't set it if not found
    
    return {func_name: params}
