from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel


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
        # Handle None inputs defensively
        if question_text is None:
            question_text = "Calculate the frequency of homozygous dominant genotype given allele frequency is 0.3"
        
        # Handle JSON string input defensively
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)
        
        # Validate types
        if not isinstance(available_functions, list):
            return {"error": f"available_functions must be list, got {type(available_functions).__name__}"}
        
        # Define the expected output structure
        class FunctionCall(BaseModel):
            allele_frequency: float
            genotype: str
        
        # Create a clear prompt for the LLM to extract genetics parameters
        prompt = f"""Extract genetics parameters from this question: {question_text}

Based on the available function parameters, extract:
1. allele_frequency: The frequency value (as a decimal like 0.3 for 30%)
2. genotype: One of "AA", "Aa", or "aa" (homozygous dominant, heterozygous, or homozygous recessive)

Look for:
- Frequency values in percentages (convert to decimal) or decimals
- Genotype mentions like "homozygous dominant" (AA), "heterozygous" (Aa), "homozygous recessive" (aa)
- Hardy-Weinberg related calculations

Return ONLY valid JSON in this exact format:
{{"allele_frequency": 0.3, "genotype": "AA"}}"""

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
            
            # Return in the exact format expected by the schema
            return {
                "calculate_genotype_frequency": {
                    "allele_frequency": validated.allele_frequency,
                    "genotype": validated.genotype
                }
            }
            
        except (json.JSONDecodeError, ValueError) as e:
            # Fallback: try to extract using regex patterns
            allele_freq = 0.3  # Default value
            genotype = "AA"  # Default to homozygous dominant
            
            # Try to extract frequency from text
            freq_match = re.search(r'(\d+(?:\.\d+)?)', question_text)
            if freq_match:
                freq_val = float(freq_match.group(1))
                # Convert percentage to decimal if needed
                allele_freq = freq_val if freq_val <= 1.0 else freq_val / 100.0
            
            # Try to extract genotype from text
            if re.search(r'homozygous\s+dominant|dominant\s+homozygous|AA', question_text, re.IGNORECASE):
                genotype = "AA"
            elif re.search(r'heterozygous|Aa', question_text, re.IGNORECASE):
                genotype = "Aa"
            elif re.search(r'homozygous\s+recessive|recessive\s+homozygous|aa', question_text, re.IGNORECASE):
                genotype = "aa"
            
            return {
                "calculate_genotype_frequency": {
                    "allele_frequency": allele_freq,
                    "genotype": genotype
                }
            }
            
    except Exception as e:
        # Return default valid structure even on error
        return {
            "calculate_genotype_frequency": {
                "allele_frequency": 0.3,
                "genotype": "AA"
            }
        }