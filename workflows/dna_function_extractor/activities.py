from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel


class FunctionCallParameters(BaseModel):
    """Expected structure for generate_DNA_sequence parameters."""
    length: int
    preferences: List[str]


class FunctionCallResult(BaseModel):
    """Wrapper for the complete function call result."""
    generate_DNA_sequence: Dict[str, Any]


async def extract_dna_function_call(
    prompt_text: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Parse the natural language prompt to extract DNA sequence generation parameters and return a structured function call.
    
    Args:
        prompt_text: The complete natural language request containing DNA sequence generation requirements including length and nucleotide preferences
        available_functions: List of function definitions available for execution to provide context for parameter extraction
    
    Returns:
        Function call structure with generate_DNA_sequence as the key and extracted parameters
    """
    try:
        # Handle JSON string input defensively
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)
        
        if not isinstance(available_functions, list):
            return {"error": f"available_functions must be list, got {type(available_functions).__name__}"}
        
        # Find the generate_DNA_sequence function definition
        generate_dna_func = None
        for func in available_functions:
            if func.get('name') == 'generate_DNA_sequence':
                generate_dna_func = func
                break
        
        if not generate_dna_func:
            return {"error": "generate_DNA_sequence function not found in available functions"}
        
        # Get parameter schema for the function
        params_schema = generate_dna_func.get('parameters', generate_dna_func.get('params', {}))
        
        # Create structured prompt for LLM to extract DNA generation parameters
        prompt = f"""Extract DNA sequence generation parameters from this user request: "{prompt_text}"

Available function: generate_DNA_sequence
Required parameters:
- length: integer (The length of the DNA sequence to be generated)
- preferences: array of nucleotide strings (Preferred nucleotides: A, T, C, G)

CRITICAL: Return ONLY valid JSON in this exact format:
{{"length": <integer>, "preferences": ["<nucleotide>", "<nucleotide>"]}}

Examples:
- "100 bp with GC preference" → {{"length": 100, "preferences": ["G", "C"]}}
- "50 nucleotides, prefer A and T" → {{"length": 50, "preferences": ["A", "T"]}}
- "200 base sequence with all nucleotides" → {{"length": 200, "preferences": ["A", "T", "C", "G"]}}

Extract from the user request and return the JSON object:"""

        # Use llm_client to extract parameters
        response = llm_client.generate(prompt)
        content = response.content.strip()

        # Remove markdown code blocks if present
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
            params_data = json.loads(content)
            validated_params = FunctionCallParameters(**params_data)
            
            # Return in the exact required format
            result = {
                "generate_DNA_sequence": validated_params.model_dump()
            }
            
            return result
            
        except (json.JSONDecodeError, ValueError) as e:
            # Fallback: try to extract using regex patterns
            length_match = re.search(r'(\d+)\s*(?:bp|base|nucleotide|nt)', prompt_text.lower())
            length = int(length_match.group(1)) if length_match else 100
            
            # Extract preferences from common patterns
            preferences = []
            if re.search(r'\b[gc]\b.*\b[gc]\b|gc|guanine.*cytosine|g.*c', prompt_text.lower()):
                preferences = ["G", "C"]
            elif re.search(r'\b[at]\b.*\b[at]\b|at|adenine.*thymine|a.*t', prompt_text.lower()):
                preferences = ["A", "T"]
            elif re.search(r'all.*nucleotide|all.*base|[atgc].*[atgc].*[atgc].*[atgc]', prompt_text.lower()):
                preferences = ["A", "T", "C", "G"]
            else:
                preferences = ["A", "T", "C", "G"]  # Default to all nucleotides
            
            return {
                "generate_DNA_sequence": {
                    "length": length,
                    "preferences": preferences
                }
            }
            
    except Exception as e:
        return {"error": f"Failed to extract DNA function call: {str(e)}"}