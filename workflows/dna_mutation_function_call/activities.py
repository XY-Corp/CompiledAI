from typing import Any, Dict, List, Optional
import asyncio
import json
import re
from pydantic import BaseModel

class DNAFunctionCall(BaseModel):
    analyze_dna_sequence: Dict[str, str]

async def extract_dna_function_call(
    prompt_text: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Parses the natural language DNA analysis request to extract sequences and parameters for the analyze_dna_sequence function call.
    
    Args:
        prompt_text: The complete natural language prompt containing DNA sequences and analysis request details
        available_functions: List of available function definitions to provide context for parameter extraction
    
    Returns:
        Function call object with analyze_dna_sequence as the key and parameters as nested object
    """
    try:
        # Handle JSON string input defensively
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)
        
        if not isinstance(available_functions, list):
            return {"error": f"available_functions must be list, got {type(available_functions).__name__}"}
        
        # Find the analyze_dna_sequence function definition
        analyze_dna_func = None
        for func in available_functions:
            if func.get('name') == 'analyze_dna_sequence':
                analyze_dna_func = func
                break
        
        if not analyze_dna_func:
            return {"error": "analyze_dna_sequence function not found in available functions"}
        
        # Get parameter schema for the function
        params_schema = analyze_dna_func.get('parameters', analyze_dna_func.get('params', {}))
        
        # Create prompt for LLM to extract DNA sequences and parameters
        prompt = f"""Extract DNA sequence analysis parameters from this user request: "{prompt_text}"

The analyze_dna_sequence function requires these exact parameters:
- sequence: The DNA sequence to analyze (string of nucleotides like AGTC)
- reference_sequence: The reference DNA sequence to compare against (string of nucleotides)
- mutation_type: Type of mutation to look for (e.g., "substitution", "insertion", "deletion")

Look for:
1. DNA sequences in the text (strings containing A, G, T, C nucleotides)
2. Which sequence is the sample and which is the reference
3. What type of mutation analysis is requested

Return ONLY valid JSON in this exact format:
{{"sequence": "AGTCGATCGAACGTACGTACG", "reference_sequence": "AGTCCATCGAACGTACGTACG", "mutation_type": "substitution"}}

Do not include any explanation, just the JSON."""

        # Use LLM to extract parameters
        response = llm_client.generate(prompt)
        
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
        
        # Parse JSON parameters
        try:
            params = json.loads(content)
            
            # Validate that we have the required parameters
            required_params = ['sequence', 'reference_sequence', 'mutation_type']
            for param in required_params:
                if param not in params:
                    return {"error": f"Missing required parameter: {param}"}
            
            # Return in the exact format specified by the schema
            result = {
                "analyze_dna_sequence": {
                    "sequence": params["sequence"],
                    "reference_sequence": params["reference_sequence"],
                    "mutation_type": params["mutation_type"]
                }
            }
            
            return result
            
        except json.JSONDecodeError as e:
            # Fallback: try to extract DNA sequences with regex
            # Look for sequences of nucleotides (A, G, T, C)
            dna_sequences = re.findall(r'[AGTC]{10,}', prompt_text.upper())
            
            if len(dna_sequences) >= 2:
                # Assume first sequence is the sample, second is reference
                sequence = dna_sequences[0]
                reference_sequence = dna_sequences[1]
                
                # Try to infer mutation type from text
                mutation_type = "substitution"  # default
                if "insertion" in prompt_text.lower():
                    mutation_type = "insertion"
                elif "deletion" in prompt_text.lower():
                    mutation_type = "deletion"
                
                result = {
                    "analyze_dna_sequence": {
                        "sequence": sequence,
                        "reference_sequence": reference_sequence,
                        "mutation_type": mutation_type
                    }
                }
                return result
            else:
                return {"error": f"Failed to parse LLM response and could not extract DNA sequences: {e}"}
                
    except Exception as e:
        return {"error": f"Failed to extract DNA function call: {e}"}