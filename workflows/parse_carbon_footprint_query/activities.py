from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel


class VehicleCallParameters(BaseModel):
    """Expected parameters for calculate_vehicle_emission function."""
    vehicle_type: str
    miles_driven: int
    emission_factor: Optional[float] = None


class VehicleFunctionCall(BaseModel):
    """Expected output structure with function name as key."""
    calculate_vehicle_emission: Dict[str, Any]


async def extract_vehicle_parameters(
    question_text: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Parse the natural language question to extract vehicle type, mileage, and optional emission factor for the calculate_vehicle_emission function.
    
    Args:
        question_text: The natural language question about vehicle carbon emissions containing vehicle type and mileage information
        available_functions: List of available function definitions to understand the expected parameter schema
    
    Returns:
        Dict with function name as key and parameters as nested object: {"calculate_vehicle_emission": {"vehicle_type": "gas", "miles_driven": 1500, "emission_factor": 355.48}}
    """
    try:
        # Handle JSON string input defensively
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)
        
        if not isinstance(available_functions, list):
            return {"error": f"available_functions must be list, got {type(available_functions).__name__}"}
        
        if not isinstance(question_text, str):
            return {"error": "question_text is required and must be a string"}
        
        # Find the calculate_vehicle_emission function in available_functions
        calc_function = None
        for func in available_functions:
            if func.get('name') == 'calculate_vehicle_emission':
                calc_function = func
                break
        
        if not calc_function:
            return {"error": "calculate_vehicle_emission function not found in available_functions"}
        
        # Get parameter schema
        params_schema = calc_function.get('parameters', {})
        properties = params_schema.get('properties', {})
        
        # Format the function schema for the LLM prompt
        param_details = []
        for param_name, param_info in properties.items():
            param_type = param_info.get('type', 'string')
            description = param_info.get('description', '')
            param_details.append(f'"{param_name}": <{param_type}> - {description}')
        
        schema_text = "{\n" + ",\n".join([f"  {detail}" for detail in param_details]) + "\n}"
        
        # Create LLM prompt
        prompt = f"""Analyze this natural language question about vehicle carbon emissions and extract the parameters needed for the calculate_vehicle_emission function.

Question: "{question_text}"

Expected parameters format:
{schema_text}

Instructions:
1. Extract vehicle_type from phrases like:
   - 'gas-powered', 'gasoline', 'gas car' -> 'gas'
   - 'diesel' -> 'diesel' 
   - 'electric', 'EV', 'electric vehicle' -> 'EV'

2. Extract miles_driven from any numerical values mentioned for miles/mileage

3. Extract emission_factor if specified, otherwise omit (uses default 355.48)

Return ONLY valid JSON in this exact format:
{{"calculate_vehicle_emission": {{"vehicle_type": "gas", "miles_driven": 1500}}}}

If emission factor is mentioned, include it:
{{"calculate_vehicle_emission": {{"vehicle_type": "gas", "miles_driven": 1500, "emission_factor": 400.0}}}}"""

        # Use LLM to extract parameters
        response = llm_client.generate(prompt)
        content = response.content.strip()
        
        # Remove markdown code blocks if present
        if "```" in content:
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
            if json_match:
                content = json_match.group(1)
            else:
                # Try to find any JSON object
                json_match = re.search(r'\{.*?\}', content, re.DOTALL)
                if json_match:
                    content = json_match.group(0)
        
        # Parse and validate JSON
        try:
            result = json.loads(content)
            
            # Validate structure using Pydantic
            validated = VehicleFunctionCall(**result)
            return validated.model_dump()
            
        except (json.JSONDecodeError, ValueError) as e:
            # Fallback: try regex extraction if JSON parsing fails
            vehicle_type = "gas"  # default
            miles_driven = 0
            emission_factor = None
            
            # Extract vehicle type with regex patterns
            text_lower = question_text.lower()
            if re.search(r'\b(electric|ev)\b', text_lower):
                vehicle_type = "EV"
            elif re.search(r'\bdiesel\b', text_lower):
                vehicle_type = "diesel"
            elif re.search(r'\b(gas|gasoline|gas-powered)\b', text_lower):
                vehicle_type = "gas"
            
            # Extract miles with regex
            miles_match = re.search(r'(\d+(?:,\d{3})*)\s*miles?', question_text, re.IGNORECASE)
            if miles_match:
                miles_str = miles_match.group(1).replace(',', '')
                miles_driven = int(miles_str)
            
            # Extract emission factor if mentioned
            emission_match = re.search(r'emission[s]?\s*factor[s]?\s*(?:of\s*)?(\d+(?:\.\d+)?)', question_text, re.IGNORECASE)
            if emission_match:
                emission_factor = float(emission_match.group(1))
            
            # Build result
            result_params = {
                "vehicle_type": vehicle_type,
                "miles_driven": miles_driven
            }
            
            if emission_factor is not None:
                result_params["emission_factor"] = emission_factor
            
            return {"calculate_vehicle_emission": result_params}
    
    except Exception as e:
        return {"error": f"Failed to extract parameters: {str(e)}"}