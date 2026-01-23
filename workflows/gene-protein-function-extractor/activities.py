from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel

async def extract_gene_function_call(
    user_query: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extracts gene name and species from user query and formats as function call parameters.
    
    Args:
        user_query: The natural language user query asking about a gene's protein sequence
        available_functions: List of available function definitions to provide context for parameter extraction
    
    Returns:
        Dict with function name as top-level key containing gene and species parameters.
        Example: {"get_protein_sequence": {"gene": "BRCA1", "species": "Homo sapiens"}}
    """
    try:
        # Handle JSON string input defensively
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)
        
        # Validate input
        if not isinstance(available_functions, list):
            return {"get_protein_sequence": {"gene": "<UNKNOWN>", "species": "Homo sapiens"}}
        
        if not available_functions:
            return {"get_protein_sequence": {"gene": "<UNKNOWN>", "species": "Homo sapiens"}}
        
        # Find the target function (likely get_protein_sequence)
        target_function = None
        for func in available_functions:
            func_name = func.get('name', '')
            if 'protein' in func_name.lower() or 'sequence' in func_name.lower():
                target_function = func
                break
        
        # Default to first function if no protein/sequence function found
        if not target_function and available_functions:
            target_function = available_functions[0]
        
        if not target_function:
            return {"get_protein_sequence": {"gene": "<UNKNOWN>", "species": "Homo sapiens"}}
        
        function_name = target_function.get('name', 'get_protein_sequence')
        
        # Create Pydantic model for validation
        class GeneParameters(BaseModel):
            gene: str
            species: str = "Homo sapiens"
        
        # Extract gene and species using LLM
        prompt = f"""Extract the gene name and species from this user request: "{user_query}"

Return ONLY valid JSON in this exact format:
{{"gene": "GENE_NAME", "species": "SPECIES_NAME"}}

Examples:
- "What is the protein sequence of BRCA1?" → {{"gene": "BRCA1", "species": "Homo sapiens"}}
- "Show me TP53 in humans" → {{"gene": "TP53", "species": "Homo sapiens"}}  
- "Get CFTR protein in mouse" → {{"gene": "CFTR", "species": "Mus musculus"}}

If species is not specified, default to "Homo sapiens".
If gene is not clear, use the most likely gene name from the query."""

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
            validated = GeneParameters(**data)
            
            # Return in the required format: {function_name: {gene: ..., species: ...}}
            return {
                function_name: validated.model_dump()
            }
            
        except (json.JSONDecodeError, ValueError) as e:
            # Fallback: try to extract gene name with regex
            gene_match = re.search(r'\b([A-Z]{2,}[0-9]*[A-Z]*)\b', user_query)
            gene = gene_match.group(1) if gene_match else "<UNKNOWN>"
            
            # Look for species mentions
            species = "Homo sapiens"  # default
            if re.search(r'\bmouse\b|\bmus musculus\b', user_query.lower()):
                species = "Mus musculus"
            elif re.search(r'\brat\b|\brattus norvegicus\b', user_query.lower()):
                species = "Rattus norvegicus"
            elif re.search(r'\bfly\b|\bdrosophila\b', user_query.lower()):
                species = "Drosophila melanogaster"
            
            return {
                function_name: {
                    "gene": gene,
                    "species": species
                }
            }
            
    except Exception as e:
        # Ultimate fallback
        return {"get_protein_sequence": {"gene": "<UNKNOWN>", "species": "Homo sapiens"}}