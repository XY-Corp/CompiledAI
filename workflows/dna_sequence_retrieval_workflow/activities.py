from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel


class DNAParametersResponse(BaseModel):
    """Schema for DNA sequence function call structure."""
    fetch_DNA_sequence: Dict[str, Any]


async def extract_dna_parameters(
    user_prompt: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extract DNA ID and optional parameters from user prompt for DNA sequence retrieval function calls.
    
    Args:
        user_prompt: The raw user prompt containing DNA sequence retrieval request
        available_functions: List of available function definitions providing context for parameter extraction
        
    Returns:
        Function call structure with fetch_DNA_sequence as top-level key and extracted parameters nested
    """
    try:
        # Handle JSON string input for available_functions defensively
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)
        
        if not isinstance(available_functions, list):
            return {"fetch_DNA_sequence": {"DNA_id": "<UNKNOWN>"}}
        
        # Find the fetch_DNA_sequence function schema
        dna_function_schema = None
        for func in available_functions:
            if func.get('name') == 'fetch_DNA_sequence':
                dna_function_schema = func
                break
        
        if not dna_function_schema:
            return {"fetch_DNA_sequence": {"DNA_id": "<UNKNOWN>"}}
        
        # Get parameter schema - handle both 'parameters' and 'params' keys
        params_schema = dna_function_schema.get('parameters', dna_function_schema.get('params', {}))
        
        # Create prompt for LLM with exact parameter names from schema
        param_details = []
        for param_name, param_info in params_schema.items():
            if isinstance(param_info, str):
                param_type = param_info
                required = True  # Assume required if just type string
            elif isinstance(param_info, dict):
                param_type = param_info.get('type', 'string')
                required = param_info.get('required', True)
            else:
                param_type = 'string'
                required = True
            
            status = "required" if required else "optional"
            param_details.append(f'"{param_name}" ({param_type}, {status})')
        
        prompt = f"""User request: "{user_prompt}"

Extract parameters for the fetch_DNA_sequence function call.

The function has these exact parameters: {', '.join(param_details)}

CRITICAL: Use EXACT parameter names: {list(params_schema.keys())}

Examples:
- "Get DNA123 sequence" → {{"DNA_id": "DNA123"}}
- "Fetch DNA456 in fasta format" → {{"DNA_id": "DNA456", "format": "fasta"}}
- "Get DNA789 with 100 upstream bases" → {{"DNA_id": "DNA789", "upstream": 100}}

Extract the DNA ID (usually starts with "DNA" or is an alphanumeric identifier).
Extract format if mentioned (fasta, genbank, etc.).
Extract upstream value if mentioned (number of bases).

Return JSON with only the extracted parameters: {{"DNA_id": "value", "format": "value", "upstream": number}}"""

        response = llm_client.generate(prompt)
        content = response.content.strip()
        
        # Extract JSON from response (handle markdown code blocks)
        if "```" in content:
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
            if json_match:
                content = json_match.group(1)
            else:
                json_match = re.search(r'\{.*?\}', content, re.DOTALL)
                if json_match:
                    content = json_match.group(0)
        
        # Parse and validate the extracted parameters
        try:
            extracted_params = json.loads(content)
            
            # Ensure we have at least DNA_id
            if not extracted_params.get('DNA_id'):
                # Try to extract DNA ID using regex as fallback
                dna_id_match = re.search(r'DNA\w*\d+|\b[A-Z0-9]+\d+\b', user_prompt, re.IGNORECASE)
                if dna_id_match:
                    extracted_params['DNA_id'] = dna_id_match.group(0)
                else:
                    extracted_params['DNA_id'] = "<UNKNOWN>"
            
            # Clean up parameters - only include valid ones from schema
            cleaned_params = {}
            for param_name in params_schema.keys():
                if param_name in extracted_params:
                    cleaned_params[param_name] = extracted_params[param_name]
            
            # Ensure DNA_id is always present
            if 'DNA_id' not in cleaned_params:
                cleaned_params['DNA_id'] = "<UNKNOWN>"
            
            # Validate with Pydantic
            validated_response = DNAParametersResponse(fetch_DNA_sequence=cleaned_params)
            return validated_response.model_dump()
            
        except (json.JSONDecodeError, ValueError) as e:
            # Fallback: try regex extraction
            dna_id_match = re.search(r'DNA\w*\d+|\b[A-Z0-9]+\d+\b', user_prompt, re.IGNORECASE)
            dna_id = dna_id_match.group(0) if dna_id_match else "<UNKNOWN>"
            
            # Look for format keywords
            format_match = re.search(r'\b(fasta|genbank|gb|embl)\b', user_prompt, re.IGNORECASE)
            extracted_format = format_match.group(1).lower() if format_match else None
            
            # Look for upstream numbers
            upstream_match = re.search(r'upstream[^\d]*(\d+)', user_prompt, re.IGNORECASE)
            extracted_upstream = int(upstream_match.group(1)) if upstream_match else None
            
            result_params = {"DNA_id": dna_id}
            if extracted_format and 'format' in params_schema:
                result_params['format'] = extracted_format
            if extracted_upstream is not None and 'upstream' in params_schema:
                result_params['upstream'] = extracted_upstream
            
            return {"fetch_DNA_sequence": result_params}
            
    except Exception as e:
        # Ultimate fallback
        return {"fetch_DNA_sequence": {"DNA_id": "<UNKNOWN>"}}