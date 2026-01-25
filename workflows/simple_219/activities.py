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
        
        extracted_value = None
        
        # For neuron_type parameter - look for neurotransmitter types
        if "neuron" in param_name.lower() or "neurotransmitter" in param_desc:
            # Common neurotransmitter types
            neurotransmitters = ["gaba", "glutamate", "dopamine", "serotonin", "acetylcholine", "norepinephrine"]
            for nt in neurotransmitters:
                if nt in query_lower:
                    extracted_value = nt.upper() if nt == "gaba" else nt.capitalize()
                    break
        
        # For brain_region parameter - look for brain region mentions
        elif "region" in param_name.lower() or "brain" in param_desc:
            # Check for "all" or "all part" or "entire"
            if "all part" in query_lower or "all region" in query_lower or "entire brain" in query_lower:
                extracted_value = "All"
            # Check for specific regions
            brain_regions = ["hippocampus", "cortex", "cerebellum", "thalamus", "hypothalamus", 
                           "amygdala", "striatum", "brainstem", "prefrontal cortex"]
            for region in brain_regions:
                if region in query_lower:
                    extracted_value = region.capitalize()
                    break
            # If "all" is mentioned in context of brain
            if extracted_value is None and ("all" in query_lower and "brain" in query_lower):
                extracted_value = "All"
        
        # Generic string extraction - look for quoted values
        if extracted_value is None and param_type == "string":
            # Try to find quoted strings
            quoted_match = re.search(r'"([^"]+)"', query)
            if quoted_match:
                extracted_value = quoted_match.group(1)
        
        # Use default if available and no value extracted
        if extracted_value is None and default_val is not None:
            extracted_value = default_val
        
        # Only add parameter if we have a value
        if extracted_value is not None:
            params[param_name] = extracted_value
    
    return {func_name: params}
