from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel

class FunctionCall(BaseModel):
    """Structure for heat capacity function call."""
    temp: int
    volume: int
    gas: str

class ExtractionResult(BaseModel):
    """Validation model for the extraction result."""
    calc_heat_capacity: Dict[str, Any]

async def extract_heat_capacity_params(
    text: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extracts temperature, volume, and gas type parameters from natural language text and formats them as a structured function call for heat capacity calculation.

    Args:
        text: The natural language request containing temperature, volume, and gas information that needs parameter extraction
        available_functions: List of function definitions providing context for parameter extraction and validation

    Returns:
        Dict with calc_heat_capacity key containing extracted parameters (temp, volume, gas)
    """
    try:
        # Parse JSON string if needed for available_functions
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)

        # Build function context for the LLM
        functions_context = "Available Functions:\n"
        for func in available_functions:
            if func.get('name') == 'calc_heat_capacity':
                # Show exact parameter names and types
                params_info = func.get('parameters', func.get('params', {}))
                param_details = []
                for param_name, param_info in params_info.items():
                    param_type = param_info.get('type', 'string') if isinstance(param_info, dict) else str(param_info)
                    param_details.append(f'"{param_name}": <{param_type}>')
                
                functions_context += f"- {func['name']}: {func.get('description', '')}\n"
                functions_context += f"  Parameters: {{{', '.join(param_details)}}}\n"
                break

        # Create LLM prompt for parameter extraction
        prompt = f"""Extract parameters for heat capacity calculation from this text: "{text}"

{functions_context}

Extract the following parameters:
- temp: temperature value (as integer, convert from any units to Kelvin if needed, default to 298 if not specified)
- volume: volume value (as integer, default to 1 if not specified)
- gas: gas type (as string, default to "air" if not specified)

Return ONLY valid JSON in this exact format:
{{"temp": 298, "volume": 10, "gas": "air"}}"""

        # Use LLM client to extract parameters
        response = llm_client.generate(prompt)
        content = response.content.strip()

        # Extract JSON from response (handle markdown code blocks)
        if "```" in content:
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
            if json_match:
                content = json_match.group(1)
            else:
                json_match = re.search(r'\{.*?\}', content, re.DOTALL)
                if json_match:
                    content = json_match.group(0)

        # Parse and validate parameters
        try:
            params_data = json.loads(content)
            
            # Validate using Pydantic model
            validated_params = FunctionCall(**params_data)
            
            # Return in the exact format specified by the schema
            result = {
                "calc_heat_capacity": validated_params.model_dump()
            }
            
            # Final validation against expected output structure
            validated_result = ExtractionResult(**result)
            return validated_result.model_dump()
            
        except (json.JSONDecodeError, ValueError) as e:
            # Fallback: try to extract values with regex
            temp = 298  # default
            volume = 1  # default
            gas = "air"  # default
            
            # Extract temperature
            temp_match = re.search(r'(\d+)\s*(?:K|kelvin|degrees?)', text, re.IGNORECASE)
            if temp_match:
                temp = int(temp_match.group(1))
            elif re.search(r'(\d+)\s*(?:C|celsius)', text, re.IGNORECASE):
                celsius_match = re.search(r'(\d+)\s*(?:C|celsius)', text, re.IGNORECASE)
                if celsius_match:
                    temp = int(celsius_match.group(1)) + 273  # Convert to Kelvin
            
            # Extract volume
            volume_match = re.search(r'(\d+)\s*(?:L|liters?|m3|cubic)', text, re.IGNORECASE)
            if volume_match:
                volume = int(volume_match.group(1))
            
            # Extract gas type
            gas_types = ["air", "nitrogen", "oxygen", "helium", "argon", "hydrogen", "carbon dioxide"]
            for gas_type in gas_types:
                if gas_type.lower() in text.lower():
                    gas = gas_type
                    break
            
            return {
                "calc_heat_capacity": {
                    "temp": temp,
                    "volume": volume,
                    "gas": gas
                }
            }
            
    except Exception as e:
        # Return default values if all extraction fails
        return {
            "calc_heat_capacity": {
                "temp": 298,
                "volume": 1,
                "gas": "air"
            }
        }