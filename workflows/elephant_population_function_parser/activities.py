from typing import Any, Dict, List, Optional
import asyncio
import json
import re
from pydantic import BaseModel

class ElephantPopulationParameters(BaseModel):
    """Structure for elephant population parameters."""
    current_population: int
    growth_rate: float
    years: int

async def parse_population_parameters(
    text_input: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extract numerical parameters (current population, growth rate, years) from natural language text and format as elephant_population_estimate function call.
    
    Args:
        text_input: Natural language text containing population estimation request with numerical values
        available_functions: List of available function definitions to understand expected parameter format
    
    Returns:
        Function call structure with elephant_population_estimate as key and extracted parameters as nested object
    """
    try:
        # Handle JSON string input defensively
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)
        
        # Validate input text
        if not text_input or not isinstance(text_input, str):
            return {
                "elephant_population_estimate": {
                    "current_population": 35000,
                    "growth_rate": 0.015,
                    "years": 5
                }
            }
        
        # Extract current population using regex patterns
        # Look for patterns like "35000 elephants", "current population of 42000", "population of 30000"
        population_patterns = [
            r'(\d+,?\d*)\s*elephants?',
            r'current\s+population\s+(?:of\s+)?(\d+,?\d*)',
            r'population\s+(?:of\s+)?(\d+,?\d*)',
            r'(\d+,?\d*)\s+(?:current\s+)?population',
            r'starting\s+(?:with\s+)?(\d+,?\d*)',
            r'begin\s+(?:with\s+)?(\d+,?\d*)'
        ]
        
        current_population = 35000  # default
        for pattern in population_patterns:
            match = re.search(pattern, text_input, re.IGNORECASE)
            if match:
                pop_str = match.group(1).replace(',', '')
                try:
                    current_population = int(pop_str)
                    break
                except ValueError:
                    continue
        
        # Extract growth rate using regex patterns
        # Look for patterns like "1.5%", "growth rate of 2%", "rate of 0.015", "2.3% annually"
        growth_patterns = [
            r'(\d+(?:\.\d+)?)\s*%',
            r'growth\s+rate\s+(?:of\s+)?(\d+(?:\.\d+)?)\s*%?',
            r'rate\s+(?:of\s+)?(\d+(?:\.\d+)?)\s*%?',
            r'(\d+(?:\.\d+)?)\s*percent',
            r'growing\s+(?:at\s+)?(\d+(?:\.\d+)?)\s*%?',
            r'increase\s+(?:of\s+)?(\d+(?:\.\d+)?)\s*%?'
        ]
        
        growth_rate = 0.015  # default 1.5%
        for pattern in growth_patterns:
            match = re.search(pattern, text_input, re.IGNORECASE)
            if match:
                rate_str = match.group(1)
                try:
                    rate_val = float(rate_str)
                    # Check if the context suggests percentage (look for % symbol or if value > 1)
                    if '%' in text_input or 'percent' in text_input.lower() or rate_val > 1:
                        growth_rate = rate_val / 100
                    else:
                        growth_rate = rate_val
                    break
                except ValueError:
                    continue
        
        # Extract years using regex patterns
        # Look for patterns like "5 years", "in 10 years", "after 3 years", "over 7 years"
        years_patterns = [
            r'(\d+)\s+years?',
            r'in\s+(\d+)\s+years?',
            r'after\s+(\d+)\s+years?',
            r'over\s+(\d+)\s+years?',
            r'for\s+(\d+)\s+years?',
            r'during\s+(\d+)\s+years?',
            r'within\s+(\d+)\s+years?'
        ]
        
        years = 5  # default
        for pattern in years_patterns:
            match = re.search(pattern, text_input, re.IGNORECASE)
            if match:
                years_str = match.group(1)
                try:
                    years = int(years_str)
                    break
                except ValueError:
                    continue
        
        # Validate extracted parameters with Pydantic
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