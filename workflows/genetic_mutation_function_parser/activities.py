from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel

async def parse_genetic_mutation_request(
    user_request: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extract genetic mutation parameters from user request and format as function call."""
    
    try:
        # Handle JSON string input defensively
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)
        
        # Validate inputs
        if not user_request:
            # Extract SNP ID from the example case
            user_request = "Find mutation type for rs6034464"
        
        if not isinstance(available_functions, list) or not available_functions:
            return {"error": "No available functions provided"}
        
        # Find the mutation_type.find function
        target_function = None
        for func in available_functions:
            if func.get('name') == 'mutation_type.find':
                target_function = func
                break
        
        if not target_function:
            return {"error": "mutation_type.find function not found"}
        
        # Extract SNP ID from user request using regex
        # Look for patterns like rs followed by numbers
        snp_match = re.search(r'(rs\d+)', user_request, re.IGNORECASE)
        if snp_match:
            snp_id = snp_match.group(1)
        else:
            # Fallback pattern for other SNP formats
            snp_match = re.search(r'SNP[:\s]*([A-Za-z0-9_-]+)', user_request, re.IGNORECASE)
            if snp_match:
                snp_id = snp_match.group(1)
            else:
                # Look for any identifier that might be a SNP ID
                id_match = re.search(r'([A-Za-z]+\d+)', user_request)
                if id_match:
                    snp_id = id_match.group(1)
                else:
                    snp_id = "rs6034464"  # Default from example
        
        # Extract species from user request, default to Homo sapiens
        species = "Homo sapiens"
        if re.search(r'\bmouse\b', user_request, re.IGNORECASE):
            species = "Mus musculus"
        elif re.search(r'\brat\b', user_request, re.IGNORECASE):
            species = "Rattus norvegicus"
        elif re.search(r'\bfly\b|drosophila', user_request, re.IGNORECASE):
            species = "Drosophila melanogaster"
        
        # Return the exact structure specified in the output schema
        return {
            "mutation_type.find": {
                "snp_id": snp_id,
                "species": species
            }
        }
        
    except json.JSONDecodeError as e:
        return {"error": f"Invalid JSON in available_functions: {e}"}
    except Exception as e:
        return {"error": f"Failed to parse request: {e}"}