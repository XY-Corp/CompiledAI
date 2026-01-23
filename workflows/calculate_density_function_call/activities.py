from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel


async def extract_density_parameters(
    prompt_text: str,
    target_function: str,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Parse the natural language prompt to extract country, year, population, and land area values needed for the calculate_density function call.
    
    Args:
        prompt_text: Natural language text containing population density calculation request with embedded data values
        target_function: Name of the target function to call (calculate_density)
        
    Returns:
        Function call structure with calculate_density as key and extracted parameters
    """
    
    class DensityParameters(BaseModel):
        """Validation model for density calculation parameters."""
        country: str
        year: str
        population: int
        land_area: int
    
    # Create a focused prompt for LLM extraction
    extraction_prompt = f"""Extract the following information from this text about population density calculation:

Text: {prompt_text}

Extract these specific values:
- country: The country name (as string)
- year: The year (as string) 
- population: The population number (as integer)
- land_area: The land area in square kilometers (as integer)

Return ONLY valid JSON in this exact format:
{{"country": "Brazil", "year": "2022", "population": 213000000, "land_area": 8500000}}"""

    response = llm_client.generate(extraction_prompt)
    
    # Extract JSON from response content
    content = response.content.strip()
    
    # Handle markdown code blocks
    if "```" in content:
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
        if json_match:
            content = json_match.group(1)
        else:
            # Try to find any JSON object
            json_match = re.search(r'\{.*?\}', content, re.DOTALL)
            if json_match:
                content = json_match.group(0)
    
    try:
        # Parse and validate the extracted data
        data = json.loads(content)
        validated = DensityParameters(**data)
        
        # Return in the required format with target_function as key
        return {
            target_function: validated.model_dump()
        }
        
    except (json.JSONDecodeError, ValueError) as e:
        # Fallback: try to extract using regex patterns
        try:
            country_match = re.search(r'(?:country|nation)[:=]?\s*"?([^",\n]+)"?', prompt_text, re.IGNORECASE)
            year_match = re.search(r'(?:year|in)\s*[:=]?\s*"?(\d{4})"?', prompt_text, re.IGNORECASE)
            population_match = re.search(r'(?:population|people)[:=]?\s*"?(\d{1,3}(?:,?\d{3})*(?:\.\d+)?)"?', prompt_text, re.IGNORECASE)
            land_area_match = re.search(r'(?:land\s*area|area|size)[:=]?\s*"?(\d{1,3}(?:,?\d{3})*(?:\.\d+)?)"?', prompt_text, re.IGNORECASE)
            
            if all([country_match, year_match, population_match, land_area_match]):
                country = country_match.group(1).strip()
                year = year_match.group(1).strip()
                population = int(population_match.group(1).replace(',', '').split('.')[0])
                land_area = int(land_area_match.group(1).replace(',', '').split('.')[0])
                
                return {
                    target_function: {
                        "country": country,
                        "year": year,
                        "population": population,
                        "land_area": land_area
                    }
                }
        except Exception:
            pass
            
        # If all else fails, return error structure
        return {
            target_function: {
                "country": "<UNKNOWN>",
                "year": "<UNKNOWN>",
                "population": 0,
                "land_area": 0
            }
        }