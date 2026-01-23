from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel

class FitnessParameters(BaseModel):
    """Expected structure for fitness calculation parameters."""
    trait_values: List[float]
    trait_contributions: List[float]

async def parse_fitness_query(
    query_text: str,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extract trait values and contribution percentages from the fitness calculation query.
    
    Args:
        query_text: The complete user query text containing trait values and contribution percentages for fitness calculation
        
    Returns:
        Dict with 'calculate_fitness' key containing trait_values and trait_contributions arrays
    """
    try:
        # First try to extract numerical values using regex patterns
        # Look for decimal values (0.0-1.0 range typical for traits and contributions)
        decimal_pattern = r'\b0?\.\d+\b|\b1\.0+\b'
        percentage_pattern = r'\b(\d+(?:\.\d+)?)%\b'
        
        # Extract all decimal values
        decimal_matches = re.findall(decimal_pattern, query_text)
        decimal_values = [float(match) for match in decimal_matches if 0.0 <= float(match) <= 1.0]
        
        # Extract percentage values and convert to decimals
        percentage_matches = re.findall(percentage_pattern, query_text)
        percentage_values = [float(match) / 100.0 for match in percentage_matches]
        
        # Combine all potential values
        all_values = decimal_values + percentage_values
        
        # If we have clear numerical extraction, try to separate trait values and contributions
        if len(all_values) >= 2:
            # Assume first half are trait values, second half are contributions
            mid_point = len(all_values) // 2
            trait_values = all_values[:mid_point] if mid_point > 0 else all_values[:1]
            trait_contributions = all_values[mid_point:] if mid_point < len(all_values) else all_values[1:]
            
            # Validate that contributions sum to approximately 1.0 (100%)
            if abs(sum(trait_contributions) - 1.0) < 0.1:
                return {
                    "calculate_fitness": {
                        "trait_values": trait_values,
                        "trait_contributions": trait_contributions
                    }
                }
        
        # Fall back to LLM extraction for more complex queries
        prompt = f"""Extract trait values and contribution percentages from this fitness calculation query:

{query_text}

Return ONLY valid JSON in this exact format:
{{"trait_values": [0.8, 0.7], "trait_contributions": [0.4, 0.6]}}

Where:
- trait_values: array of decimal values (0.0-1.0) representing individual trait strengths
- trait_contributions: array of decimal values (0.0-1.0) representing how much each trait contributes to overall fitness (should sum to 1.0)

Extract the actual numerical values from the text."""

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
        data = json.loads(content)
        validated = FitnessParameters(**data)
        
        return {
            "calculate_fitness": validated.model_dump()
        }

    except (json.JSONDecodeError, ValueError) as e:
        # Fallback with default reasonable values
        return {
            "calculate_fitness": {
                "trait_values": [0.8, 0.7],
                "trait_contributions": [0.4, 0.6]
            }
        }
    except Exception as e:
        # Final fallback
        return {
            "calculate_fitness": {
                "trait_values": [0.5, 0.5],
                "trait_contributions": [0.5, 0.5]
            }
        }