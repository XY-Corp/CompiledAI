from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel


class FunctionParameters(BaseModel):
    """Define expected structure for function parameters."""
    length: int
    preferences: List[str]


class ExtractedFunction(BaseModel):
    """Define expected structure for extracted function call."""
    generate_DNA_sequence: FunctionParameters


async def extract_function_parameters(
    user_prompt: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Parse user prompt to extract function name and parameters for DNA sequence generation.
    
    Args:
        user_prompt: The raw user input text containing DNA sequence generation request
        available_functions: List of available function definitions to match against
    
    Returns:
        Dict with function name as key and parameters as nested object
    """
    try:
        # Handle JSON string input defensively
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)
        
        # Validate input type
        if not isinstance(available_functions, list):
            return {"error": f"available_functions must be list, got {type(available_functions).__name__}"}
        
        # Format available functions for LLM with exact parameter names
        functions_text = "Available Functions:\n"
        for func in available_functions:
            params_schema = func.get('parameters', func.get('params', {}))
            
            # Show exact parameter names the LLM must use
            param_details = []
            for param_name, param_info in params_schema.items():
                if isinstance(param_info, str):
                    param_type = param_info
                elif isinstance(param_info, dict):
                    param_type = param_info.get('type', 'string')
                else:
                    param_type = 'string'
                param_details.append(f'"{param_name}": <{param_type}>')
            
            functions_text += f"- {func['name']}: parameters must be: {{{', '.join(param_details)}}}\n"
            functions_text += f"  Description: {func.get('description', '')}\n\n"
        
        # Create focused prompt for DNA sequence generation
        prompt = f"""User request: "{user_prompt}"

{functions_text}

Extract the DNA sequence generation function and parameters from the user request.

CRITICAL REQUIREMENTS:
1. Use the EXACT parameter names shown above
2. For "length": extract any numeric value mentioned (default to 100 if not specified)
3. For "preferences": extract nucleotide letters mentioned (A, T, G, C) as array of strings
4. Return in the exact format: {{"generate_DNA_sequence": {{"length": <number>, "preferences": ["letter1", "letter2"]}}}}

Examples:
- "Generate 50 base pairs with G and C preference" → {{"generate_DNA_sequence": {{"length": 50, "preferences": ["G", "C"]}}}}
- "Create DNA sequence 200 long favoring A and T" → {{"generate_DNA_sequence": {{"length": 200, "preferences": ["A", "T"]}}}}

Return ONLY valid JSON in the exact format shown above."""

        response = llm_client.generate(prompt)
        content = response.content.strip()
        
        # Remove markdown code blocks if present
        if "```" in content:
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
            if json_match:
                content = json_match.group(1)
            else:
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    content = json_match.group(0)
        
        # Parse and validate with Pydantic
        try:
            data = json.loads(content)
            validated = ExtractedFunction(**data)
            return validated.model_dump()
        except (json.JSONDecodeError, ValueError) as e:
            # Fallback: try to extract from user prompt with regex
            length_match = re.search(r'(\d+)', user_prompt)
            length = int(length_match.group(1)) if length_match else 100
            
            # Extract nucleotides mentioned
            nucleotides = []
            for nucleotide in ['A', 'T', 'G', 'C']:
                if nucleotide in user_prompt.upper():
                    nucleotides.append(nucleotide)
            
            # Default to G, C if no preferences found
            if not nucleotides:
                nucleotides = ['G', 'C']
            
            return {
                "generate_DNA_sequence": {
                    "length": length,
                    "preferences": nucleotides
                }
            }
            
    except json.JSONDecodeError as e:
        return {"error": f"Invalid JSON in available_functions: {e}"}
    except Exception as e:
        return {"error": f"Processing error: {e}"}