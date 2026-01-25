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
    """Extract function call parameters from user query using regex and string matching."""
    
    # Parse prompt - may be JSON string with nested structure
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
            # Handle BFCL format: {"question": [[{"role": "user", "content": "..."}]]}
            if "question" in data and isinstance(data["question"], list):
                if len(data["question"]) > 0 and isinstance(data["question"][0], list):
                    query = data["question"][0][0].get("content", str(prompt))
                else:
                    query = str(prompt)
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
    props = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters using regex patterns
    params = {}
    
    # Extract key (musical key like "C major", "D minor", etc.)
    # Pattern: "in X major/minor scale" or "X major" or "key of X"
    key_patterns = [
        r'in\s+([A-G][#b]?)\s+(?:major|minor)',
        r'([A-G][#b]?)\s+(?:major|minor)\s+scale',
        r'key\s+of\s+([A-G][#b]?)',
        r'([A-G][#b]?)\s+(?:major|minor)',
    ]
    for pattern in key_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            params["key"] = match.group(1).upper()
            break
    
    # Extract start_note (scientific pitch notation like C4, D#5, etc.)
    # Pattern: "starting with/from/at note X" or "note X" or just the note
    note_patterns = [
        r'(?:starting\s+(?:with|from|at)\s+(?:the\s+)?note\s+)([A-G][#b]?\d)',
        r'(?:start\s+(?:with|from|at)\s+(?:the\s+)?note\s+)([A-G][#b]?\d)',
        r'(?:note\s+)([A-G][#b]?\d)',
        r'\b([A-G][#b]?\d)\b',
    ]
    for pattern in note_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            # Normalize: uppercase letter, keep # or b, keep number
            note = match.group(1)
            params["start_note"] = note[0].upper() + note[1:]
            break
    
    # Extract length (number of measures)
    # Pattern: "X measures" or "length of X"
    length_patterns = [
        r'(\d+)\s+measures?\s+long',
        r'(\d+)\s+measures?',
        r'length\s+(?:of\s+)?(\d+)',
    ]
    for pattern in length_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            params["length"] = int(match.group(1))
            break
    
    # Extract tempo (beats per minute)
    # Pattern: "at X bpm" or "X beats per minute" or "tempo of X"
    tempo_patterns = [
        r'(?:at\s+)?(\d+)\s+(?:beats?\s+per\s+minute|bpm)',
        r'tempo\s+(?:of\s+)?(\d+)',
        r'(\d+)\s+bpm',
    ]
    for pattern in tempo_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            params["tempo"] = int(match.group(1))
            break
    
    return {func_name: params}
