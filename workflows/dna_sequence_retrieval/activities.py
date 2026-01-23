from typing import Any, Dict, List, Optional
import asyncio
import json
import re
from pydantic import BaseModel

async def parse_dna_request(
    prompt: str,
    functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extract DNA sequence retrieval parameters from user request using LLM analysis.
    
    Args:
        prompt: The raw user request containing DNA ID and optional parameters for sequence retrieval
        functions: List of available functions with their parameter specifications for context
        
    Returns:
        Function call structure with fetch_DNA_sequence as key and extracted parameters
    """
    try:
        # Handle JSON string input for functions defensively
        if isinstance(functions, str):
            functions = json.loads(functions)
        
        if not isinstance(functions, list):
            return {"fetch_DNA_sequence": {"DNA_id": "<UNKNOWN>"}}
        
        # Find the fetch_DNA_sequence function schema
        dna_function_schema = None
        for func in functions:
            if func.get('name') == 'fetch_DNA_sequence':
                dna_function_schema = func
                break
        
        if not dna_function_schema:
            return {"fetch_DNA_sequence": {"DNA_id": "<UNKNOWN>"}}
        
        # Get parameter schema - handle both 'parameters' and 'params' keys
        params_schema = dna_function_schema.get('parameters', dna_function_schema.get('params', {}))
        
        # Build clear parameter specification for LLM
        param_details = []
        for param_name, param_info in params_schema.items():
            if isinstance(param_info, str):
                param_type = param_info
                description = f"{param_name} ({param_type})"
            elif isinstance(param_info, dict):
                param_type = param_info.get('type', 'string')
                param_desc = param_info.get('description', '')
                description = f"{param_name} ({param_type}): {param_desc}"
            else:
                description = f"{param_name} (string)"
            param_details.append(description)
        
        # Create LLM prompt to extract DNA parameters
        llm_prompt = f"""Extract DNA sequence retrieval parameters from this user request: "{prompt}"

Available parameters for fetch_DNA_sequence:
{chr(10).join(f"- {detail}" for detail in param_details)}

Return ONLY valid JSON in this format:
{{"DNA_id": "extracted_id", "format": "fasta", "upstream": 0}}

Include only the parameters that can be extracted from the request. DNA_id is always required.
For optional parameters, only include them if explicitly mentioned in the request."""

        response = llm_client.generate(llm_prompt)
        
        # Extract JSON from response (handles markdown code blocks)
        content = response.content.strip()
        
        # Remove markdown code blocks if present
        if "```" in content:
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
            if json_match:
                content = json_match.group(1)
            else:
                # Try to find any JSON object
                json_match = re.search(r'\{.*?\}', content, re.DOTALL)
                if json_match:
                    content = json_match.group(0)
        
        # Parse the JSON response
        try:
            extracted_params = json.loads(content)
            
            # Ensure we have at least DNA_id
            if not extracted_params.get('DNA_id'):
                # Try to extract DNA_id from original prompt using regex
                dna_id_match = re.search(r'\b(DNA\d+|[A-Z]+\d+)\b', prompt, re.IGNORECASE)
                if dna_id_match:
                    extracted_params['DNA_id'] = dna_id_match.group(0)
                else:
                    extracted_params['DNA_id'] = "<UNKNOWN>"
            
            return {"fetch_DNA_sequence": extracted_params}
            
        except json.JSONDecodeError:
            # Fallback: try to extract DNA_id with regex
            dna_id_match = re.search(r'\b(DNA\d+|[A-Z]+\d+)\b', prompt, re.IGNORECASE)
            dna_id = dna_id_match.group(0) if dna_id_match else "<UNKNOWN>"
            return {"fetch_DNA_sequence": {"DNA_id": dna_id}}
            
    except Exception as e:
        # Fallback error handling
        return {"fetch_DNA_sequence": {"DNA_id": "<UNKNOWN>"}}