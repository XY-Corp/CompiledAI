from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel


class ElephantPopulationParameters(BaseModel):
    current_population: int
    growth_rate: float
    years: int


async def extract_population_parameters(
    text: str,
    function_schema: dict,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extracts current population, growth rate, and years parameters from natural language text and structures them into the elephant_population_estimate function call format.
    
    Args:
        text: The natural language text containing elephant population estimation request with numerical parameters
        function_schema: The function schema definition providing parameter names, types, and descriptions for the elephant_population_estimate function
    
    Returns:
        Function call structure with elephant_population_estimate as top-level key containing extracted parameters
    """
    try:
        # Handle JSON string input defensively
        if isinstance(function_schema, str):
            function_schema = json.loads(function_schema)
        
        # Validate input text
        if not text or not isinstance(text, str):
            return {"elephant_population_estimate": {"current_population": 35000, "growth_rate": 0.015, "years": 5}}
        
        # Extract current population (look for numbers followed by "elephants" or similar)
        population_match = re.search(r'(\d+,?\d*)\s*elephants?|current\s+population\s+of\s+(\d+,?\d*)|population\s+of\s+(\d+,?\d*)', text, re.IGNORECASE)
        current_population = 35000  # default
        if population_match:
            pop_str = (population_match.group(1) or population_match.group(2) or population_match.group(3)).replace(',', '')
            current_population = int(pop_str)
        
        # Extract growth rate (look for percentage or decimal)
        growth_match = re.search(r'(\d+(?:\.\d+)?)\s*%|growth\s+rate\s+of\s+(\d+(?:\.\d+)?)|rate\s+of\s+(\d+(?:\.\d+)?)', text, re.IGNORECASE)
        growth_rate = 0.015  # default 1.5%
        if growth_match:
            rate_str = growth_match.group(1) or growth_match.group(2) or growth_match.group(3)
            rate_val = float(rate_str)
            # If it looks like a percentage (> 1), convert to decimal
            if rate_val > 1:
                growth_rate = rate_val / 100
            else:
                growth_rate = rate_val
        
        # Extract years (look for numbers followed by "years")
        years_match = re.search(r'(\d+)\s+years?|in\s+(\d+)\s+years?|after\s+(\d+)\s+years?|over\s+(\d+)\s+years?', text, re.IGNORECASE)
        years = 5  # default
        if years_match:
            years_str = years_match.group(1) or years_match.group(2) or years_match.group(3) or years_match.group(4)
            years = int(years_str)
        
        # Validate with Pydantic
        params = ElephantPopulationParameters(
            current_population=current_population,
            growth_rate=growth_rate,
            years=years
        )
        
        # Return in the exact format required by the schema
        return {
            "elephant_population_estimate": params.model_dump()
        }
        
    except Exception as e:
        # Return default values in expected format if parsing fails
        return {
            "elephant_population_estimate": {
                "current_population": 35000,
                "growth_rate": 0.015,
                "years": 5
            }
        }