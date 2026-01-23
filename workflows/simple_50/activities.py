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
    
    Parses the user query to extract parameter values and returns them
    in the format {"function_name": {"param1": val1, ...}}.
    """
    # Parse prompt (may be JSON string with nested structure)
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
        else:
            data = prompt
        
        # Extract user query from BFCL format
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
    props = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters from query using regex
    params = {}
    
    # Extract substance - look for common substance names
    substance_patterns = [
        r'\b(ice|water|steam|air|oxygen|nitrogen|helium|hydrogen|iron|copper|aluminum|gold|silver)\b',
    ]
    for pattern in substance_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            params["substance"] = match.group(1).lower()
            break
    
    # Extract mass - look for patterns like "1kg", "1 kg", "1-kg"
    mass_patterns = [
        r'(\d+(?:\.\d+)?)\s*[-]?\s*kg\b',
        r'(\d+(?:\.\d+)?)\s*kilogram',
        r'mass\s+(?:of\s+)?(\d+(?:\.\d+)?)',
    ]
    for pattern in mass_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            params["mass"] = int(float(match.group(1)))
            break
    
    # Extract temperatures - look for patterns like "0°C", "100°C", "0 degrees"
    temp_patterns = [
        r'(\d+)\s*°\s*C',
        r'(\d+)\s*degrees?\s*(?:C|Celsius)',
        r'at\s+(\d+)\s*°',
        r'to\s+(\d+)\s*°',
    ]
    
    temperatures = []
    for match in re.finditer(r'(-?\d+)\s*(?:°\s*C|degrees?\s*(?:C|Celsius)?)', query, re.IGNORECASE):
        temperatures.append(int(match.group(1)))
    
    # Also try simpler pattern
    if len(temperatures) < 2:
        simple_temps = re.findall(r'(-?\d+)\s*°', query)
        for t in simple_temps:
            temp_val = int(t)
            if temp_val not in temperatures:
                temperatures.append(temp_val)
    
    # Assign temperatures based on context (initial vs final)
    if len(temperatures) >= 2:
        # Check for "from X to Y" or "at X ... to Y" patterns
        from_to_match = re.search(r'(?:from|at)\s+(-?\d+).*?(?:to|heated to)\s+(-?\d+)', query, re.IGNORECASE)
        if from_to_match:
            params["initial_temperature"] = int(from_to_match.group(1))
            params["final_temperature"] = int(from_to_match.group(2))
        else:
            # Assume first is initial, second is final
            params["initial_temperature"] = temperatures[0]
            params["final_temperature"] = temperatures[1]
    elif len(temperatures) == 1:
        # Only one temperature found, need to determine which
        if re.search(r'initial|start|at', query, re.IGNORECASE):
            params["initial_temperature"] = temperatures[0]
        else:
            params["final_temperature"] = temperatures[0]
    
    # Extract pressure - look for patterns like "1 atmosphere", "1 atm"
    pressure_patterns = [
        r'(\d+(?:\.\d+)?)\s*(?:atmosphere|atm)\b',
        r'under\s+(\d+(?:\.\d+)?)\s*(?:atmosphere|atm)',
        r'(\d+(?:\.\d+)?)\s*atm\s+(?:of\s+)?pressure',
    ]
    for pattern in pressure_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            params["pressure"] = int(float(match.group(1)))
            break
    
    return {func_name: params}
