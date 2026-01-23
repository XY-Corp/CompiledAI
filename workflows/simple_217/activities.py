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
            # Handle BFCL format: {"question": [[{"role": "user", "content": "..."}]], ...}
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
    
    # Parse functions (may be JSON string)
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
    props = func.get("parameters", {}).get("properties", {})
    
    params = {}
    
    # Extract data_source - look for file paths
    if "data_source" in props:
        # Match paths like ~/data/file.nii, /path/to/file, etc.
        path_match = re.search(r'(~/[^\s,]+|/[^\s,]+\.[a-zA-Z]+)', query)
        if path_match:
            params["data_source"] = path_match.group(1)
    
    # Extract sequence_type - look for sequence type mentions
    if "sequence_type" in props:
        # Common fMRI sequence types
        sequence_patterns = [
            r'multi-band',
            r'multiband',
            r'single-band',
            r'EPI',
            r'BOLD',
            r'resting[- ]?state',
            r'task[- ]?based',
        ]
        for pattern in sequence_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                params["sequence_type"] = match.group(0)
                break
    
    # Extract smooth - look for smoothing value in mm
    if "smooth" in props:
        # Match patterns like "smoothed at 6mm", "6mm smoothing", "smooth 6mm"
        smooth_patterns = [
            r'smooth(?:ed|ing)?\s+(?:at\s+)?(\d+)\s*mm',
            r'(\d+)\s*mm\s+smooth',
            r'FWHM\s*(?:of\s+)?(\d+)',
        ]
        for pattern in smooth_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                params["smooth"] = int(match.group(1))
                break
    
    # Extract voxel_size - look for voxel size in mm
    if "voxel_size" in props:
        # Match patterns like "voxel size of 2mm", "2mm isotropic voxel"
        voxel_patterns = [
            r'(?:isotropic\s+)?voxel\s+size\s+(?:of\s+)?(\d+)\s*mm',
            r'(\d+)\s*mm\s+(?:isotropic\s+)?voxel',
            r'isotropic\s+(?:voxel\s+)?(?:size\s+)?(?:of\s+)?(\d+)\s*mm',
        ]
        for pattern in voxel_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                params["voxel_size"] = int(match.group(1))
                break
    
    return {func_name: params}
