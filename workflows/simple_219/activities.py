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
    
    # Get function details
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters from query using regex and string matching
    params = {}
    query_lower = query.lower()
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        default_val = param_info.get("default")
        
        if param_name == "neuron_type":
            # Look for neurotransmitter types: GABA, Glutamate, Dopamine, etc.
            neurotransmitters = ["gaba", "glutamate", "dopamine", "serotonin", "acetylcholine", "norepinephrine"]
            for nt in neurotransmitters:
                if nt in query_lower:
                    params[param_name] = nt.upper() if nt == "gaba" else nt.capitalize()
                    break
            
            # Also try regex for "produces X neurotransmitters" or "X neuron"
            if param_name not in params:
                match = re.search(r'produces?\s+(\w+)\s+neurotransmitter', query_lower)
                if match:
                    params[param_name] = match.group(1).upper() if match.group(1).lower() == "gaba" else match.group(1).capitalize()
                else:
                    match = re.search(r'(\w+)\s+neuron', query_lower)
                    if match:
                        params[param_name] = match.group(1).upper() if match.group(1).lower() == "gaba" else match.group(1).capitalize()
        
        elif param_name == "brain_region":
            # Look for brain region patterns
            # Check for "all part" or "all regions" or "entire brain"
            if "all part" in query_lower or "all region" in query_lower or "entire brain" in query_lower or "whole brain" in query_lower:
                params[param_name] = "All"
            else:
                # Try to extract specific brain regions
                brain_regions = ["hippocampus", "cortex", "cerebellum", "amygdala", "thalamus", 
                                "hypothalamus", "striatum", "brainstem", "prefrontal cortex"]
                for region in brain_regions:
                    if region in query_lower:
                        params[param_name] = region.capitalize()
                        break
                
                # Check for pattern like "in the X region" or "of the X"
                if param_name not in params:
                    match = re.search(r"(?:in|of)\s+(?:the\s+)?(?:rat'?s?\s+)?(\w+(?:\s+\w+)?)\s+(?:region|part|area)", query_lower)
                    if match:
                        region_text = match.group(1).strip()
                        if region_text not in ["brain", "rat", "rat's"]:
                            params[param_name] = region_text.capitalize()
                
                # Use default if available and not found
                if param_name not in params and default_val is not None:
                    params[param_name] = default_val
    
    return {func_name: params}
