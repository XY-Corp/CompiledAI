from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel

async def extract_gene_function_call(
    user_prompt: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extract gene name and species from user prompt and generate the appropriate function call structure.
    
    Args:
        user_prompt: The user's natural language request for gene protein sequence identification
        available_functions: List of available function definitions to provide context for parameter extraction
    
    Returns:
        Dict with function name as key and parameters dict as value. 
        Example: {"get_protein_sequence": {"gene": "BRCA1", "species": "Homo sapiens"}}
    """
    try:
        # Handle JSON string input defensively
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)
        
        # Validate input
        if not isinstance(available_functions, list) or not available_functions:
            return {"get_protein_sequence": {"gene": "<UNKNOWN>", "species": "Homo sapiens"}}
        
        # Get the function definition (assuming it's get_protein_sequence)
        target_function = None
        for func in available_functions:
            if func.get('name') == 'get_protein_sequence':
                target_function = func
                break
        
        if not target_function:
            return {"get_protein_sequence": {"gene": "<UNKNOWN>", "species": "Homo sapiens"}}
        
        # Create Pydantic model for validation
        class FunctionCall(BaseModel):
            gene: str
            species: str = "Homo sapiens"
        
        # Create prompt for LLM to extract gene and species
        prompt = f"""Extract the gene name and species from this user request: "{user_prompt}"

The user is asking about protein sequence identification. Extract:
1. Gene name (required) - look for gene symbols like BRCA1, TP53, EGFR, etc.
2. Species (optional, defaults to "Homo sapiens") - look for species names like "human", "mouse", "rat", etc.

If no gene is mentioned, use "BRCA1" as example.
If no species is mentioned, use "Homo sapiens".

Return ONLY valid JSON in this exact format:
{{"gene": "GENE_SYMBOL", "species": "Species name"}}

Examples:
- "What's the protein sequence for BRCA1?" → {{"gene": "BRCA1", "species": "Homo sapiens"}}
- "Get TP53 sequence in mouse" → {{"gene": "TP53", "species": "Mus musculus"}}
- "Show me EGFR protein" → {{"gene": "EGFR", "species": "Homo sapiens"}}"""

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
        
        # Parse and validate with Pydantic
        try:
            data = json.loads(content)
            validated = FunctionCall(**data)
            
            # Return in the exact format specified by the schema
            return {
                "get_protein_sequence": {
                    "gene": validated.gene,
                    "species": validated.species
                }
            }
        except (json.JSONDecodeError, ValueError) as e:
            # Fallback: try to extract gene with regex patterns
            gene_match = re.search(r'\b([A-Z][A-Z0-9]{2,})\b', user_prompt)
            gene = gene_match.group(1) if gene_match else "BRCA1"
            
            # Check for species mentions
            species = "Homo sapiens"
            if re.search(r'\b(mouse|mice|mus musculus)\b', user_prompt.lower()):
                species = "Mus musculus"
            elif re.search(r'\b(rat|rattus)\b', user_prompt.lower()):
                species = "Rattus norvegicus"
            elif re.search(r'\b(human|homo sapiens)\b', user_prompt.lower()):
                species = "Homo sapiens"
            
            return {
                "get_protein_sequence": {
                    "gene": gene,
                    "species": species
                }
            }
            
    except Exception as e:
        # Final fallback - return default values
        return {
            "get_protein_sequence": {
                "gene": "BRCA1", 
                "species": "Homo sapiens"
            }
        }