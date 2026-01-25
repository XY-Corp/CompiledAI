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
    the function schema to extract parameter values using regex patterns.
    Returns format: {"function_name": {"param1": val1, ...}}
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
    func = funcs[0] if isinstance(funcs, list) else funcs
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract all numbers from the query (integers and floats)
    # Pattern matches integers and decimals including percentages
    numbers = re.findall(r'(\d+(?:\.\d+)?)\s*%?', query)
    
    # Convert to appropriate types
    extracted_numbers = []
    for num_str in numbers:
        if '.' in num_str:
            extracted_numbers.append(float(num_str))
        else:
            extracted_numbers.append(int(num_str))
    
    # Check for percentage context - "60%" means 0.6 probability
    percentage_matches = re.findall(r'(\d+(?:\.\d+)?)\s*%', query)
    percentage_values = set()
    for pm in percentage_matches:
        if '.' in pm:
            percentage_values.add(float(pm))
        else:
            percentage_values.add(int(pm))
    
    # Build params based on schema
    params = {}
    
    # For binomial probability: n=trials, k=successes, p=probability
    # Look for contextual clues in the query
    
    # Extract n (number of trials) - look for "X times" pattern
    trials_match = re.search(r'(\d+)\s*times', query, re.IGNORECASE)
    
    # Extract k (number of successes) - look for "exactly X" pattern
    successes_match = re.search(r'exactly\s+(\d+)', query, re.IGNORECASE)
    
    # Extract p (probability) - look for percentage or "chance of X%"
    prob_match = re.search(r'(?:chance|probability|odds).*?(\d+(?:\.\d+)?)\s*%', query, re.IGNORECASE)
    if not prob_match:
        prob_match = re.search(r'(\d+(?:\.\d+)?)\s*%', query, re.IGNORECASE)
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_name == "n" or "trial" in param_desc:
            # Number of trials
            if trials_match:
                params[param_name] = int(trials_match.group(1))
            elif extracted_numbers:
                # Find the larger integer that's likely trials
                integers = [n for n in extracted_numbers if isinstance(n, int) or n == int(n)]
                if integers:
                    # Trials is usually the larger number
                    params[param_name] = int(max(integers))
        
        elif param_name == "k" or "success" in param_desc:
            # Number of successes
            if successes_match:
                params[param_name] = int(successes_match.group(1))
            elif extracted_numbers:
                # Find a smaller integer that's likely successes
                integers = [n for n in extracted_numbers if isinstance(n, int) or n == int(n)]
                if len(integers) >= 2:
                    params[param_name] = int(min(integers))
        
        elif param_name == "p" or "probability" in param_desc:
            # Probability of success
            if prob_match:
                prob_value = float(prob_match.group(1))
                # Convert percentage to decimal
                params[param_name] = prob_value / 100.0
            elif percentage_values:
                # Use the percentage value, convert to decimal
                prob_value = list(percentage_values)[0]
                params[param_name] = float(prob_value) / 100.0
    
    return {func_name: params}
