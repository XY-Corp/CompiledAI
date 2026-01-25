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
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters from query
    params = {}
    
    # Extract chord progression - look for patterns like "C, F and G" or "C, F, G"
    # Pattern: letters that are chord names (A-G with optional sharps/flats/modifiers)
    chord_pattern = r'\b([A-G][#b]?(?:m|maj|min|dim|aug|7|9|11|13)?)\b'
    
    # Look for progression context
    progression_match = re.search(r'progression\s+(?:of\s+)?([A-G][^.]*?)(?:\s+for|\s+in|\s+with|\.)', query, re.IGNORECASE)
    if progression_match:
        chord_text = progression_match.group(1)
        chords = re.findall(chord_pattern, chord_text)
    else:
        # Try to find chords mentioned with "and" or commas
        chord_section_match = re.search(r'(?:with|of)\s+([A-G][^.]*?)(?:\s+for|\s+in|\.)', query, re.IGNORECASE)
        if chord_section_match:
            chord_text = chord_section_match.group(1)
            chords = re.findall(chord_pattern, chord_text)
        else:
            # Fallback: find all chord-like patterns
            chords = re.findall(chord_pattern, query)
    
    if chords and "progression" in params_schema:
        params["progression"] = chords
    
    # Extract measures - look for number followed by "measures" or "bars"
    measures_match = re.search(r'(\d+)\s*(?:measures?|bars?)', query, re.IGNORECASE)
    if measures_match and "measures" in params_schema:
        params["measures"] = int(measures_match.group(1))
    else:
        # Fallback: look for any number in context
        numbers = re.findall(r'\b(\d+)\b', query)
        if numbers and "measures" in params_schema:
            params["measures"] = int(numbers[0])
    
    # Extract instrument - look for common instrument names
    instruments = ["piano", "guitar", "violin", "drums", "bass", "flute", "trumpet", "saxophone", "cello", "organ"]
    query_lower = query.lower()
    
    for instrument in instruments:
        if instrument in query_lower:
            if "instrument" in params_schema:
                params["instrument"] = instrument.capitalize()
            break
    
    # If instrument not found but mentioned in schema with default, use default
    if "instrument" not in params and "instrument" in params_schema:
        # Check if there's a default in the description
        instrument_desc = params_schema.get("instrument", {}).get("description", "")
        if "Default is" in instrument_desc:
            default_match = re.search(r"Default is '(\w+)'", instrument_desc)
            if default_match:
                params["instrument"] = default_match.group(1)
    
    return {func_name: params}
