from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel, Field

class GeneticsParameterExtraction(BaseModel):
    """Expected structure for genetics parameter extraction."""
    calculate_genotype_frequency: Dict[str, Any] = Field(
        description="Function call with allele frequency and genotype parameters"
    )

async def extract_genetics_parameters(
    question_text: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extract allele frequency and genotype parameters from genetics question text and return the function call structure.
    
    Args:
        question_text: The genetics question text containing allele frequency and genotype information to extract parameters from
        available_functions: List of available function definitions to guide parameter extraction and function selection
        
    Returns:
        Dict with calculate_genotype_frequency as the top-level key containing allele_frequency (float) and genotype (string) parameters
    """
    try:
        # Handle JSON string input defensively
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)
        
        # Validate types
        if not isinstance(available_functions, list):
            return {"error": f"available_functions must be list, got {type(available_functions).__name__}"}
        
        # Create a clear prompt for the LLM to extract genetics parameters
        prompt = f"""Extract genetics parameters from this question: {question_text}

Available function: calculate_genotype_frequency
Required parameters:
- allele_frequency: float (frequency of the allele, between 0 and 1)
- genotype: string (genotype to calculate frequency for, like "AA", "Aa", or "aa")

Look for:
- Allele frequencies mentioned in the text (e.g., "frequency of 0.3", "30% frequency")
- Genotype types being asked about (homozygous dominant "AA", heterozygous "Aa", homozygous recessive "aa")

Return ONLY valid JSON in this exact format:
{{"calculate_genotype_frequency": {{"allele_frequency": 0.3, "genotype": "AA"}}}}"""

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
            validated = GeneticsParameterExtraction(**data)
            return validated.model_dump()
        except (json.JSONDecodeError, ValueError) as e:
            # Fallback: try to extract parameters with regex patterns
            return _fallback_extraction(question_text)
            
    except Exception as e:
        return {"error": f"Failed to extract genetics parameters: {e}"}

def _fallback_extraction(question_text: str) -> dict[str, Any]:
    """Fallback extraction using regex patterns."""
    try:
        # Extract allele frequency patterns
        allele_freq = 0.5  # default
        freq_patterns = [
            r'frequency[^0-9]*([0-9]*\.?[0-9]+)',
            r'([0-9]*\.?[0-9]+)[^0-9]*frequency',
            r'([0-9]*\.?[0-9]+)%',
            r'p\s*=\s*([0-9]*\.?[0-9]+)',
            r'allele.*?([0-9]*\.?[0-9]+)'
        ]
        
        for pattern in freq_patterns:
            match = re.search(pattern, question_text.lower())
            if match:
                freq_value = float(match.group(1))
                # Convert percentage to decimal if needed
                if freq_value > 1.0:
                    freq_value = freq_value / 100.0
                allele_freq = freq_value
                break
        
        # Extract genotype patterns
        genotype = "AA"  # default to homozygous dominant
        genotype_patterns = [
            (r'\bAA\b', "AA"),
            (r'\bAa\b', "Aa"),
            (r'\baa\b', "aa"),
            (r'homozygous dominant', "AA"),
            (r'homozygous recessive', "aa"),
            (r'heterozygous', "Aa"),
            (r'dominant.*homozygous', "AA"),
            (r'recessive.*homozygous', "aa")
        ]
        
        for pattern, gt in genotype_patterns:
            if re.search(pattern, question_text, re.IGNORECASE):
                genotype = gt
                break
        
        return {
            "calculate_genotype_frequency": {
                "allele_frequency": allele_freq,
                "genotype": genotype
            }
        }
    except Exception as e:
        # Final fallback with default values
        return {
            "calculate_genotype_frequency": {
                "allele_frequency": 0.5,
                "genotype": "AA"
            }
        }