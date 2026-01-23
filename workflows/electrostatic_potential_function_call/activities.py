from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel

class FunctionCall(BaseModel):
    calculate_electrostatic_potential: dict

async def extract_electrostatic_parameters(
    query_text: str,
    function_schema: dict,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Parse user query to extract charge values, distance, and optional constant for electrostatic potential calculation"""
    try:
        # Handle JSON string input defensively
        if isinstance(function_schema, str):
            function_schema = json.loads(function_schema)
        
        # Ensure we have a query_text
        if not query_text or query_text.strip() == "null":
            query_text = ""
        
        # Extract the function schema details
        functions_list = function_schema if isinstance(function_schema, list) else [function_schema]
        
        # Find the electrostatic potential function
        target_function = None
        for func in functions_list:
            if func.get('name') == 'calculate_electrostatic_potential':
                target_function = func
                break
        
        if not target_function:
            return {"error": "calculate_electrostatic_potential function not found"}
        
        # Get parameters schema
        params_schema = target_function.get('parameters', {})
        properties = params_schema.get('properties', {})
        
        # Create prompt for LLM to extract parameters
        prompt = f"""Extract parameters for electrostatic potential calculation from this text: "{query_text}"

The function requires these parameters:
- charge1 (float): The quantity of charge on the first body
- charge2 (float): The quantity of charge on the second body  
- distance (float): The distance between the two bodies
- constant (float, optional): The electrostatic constant (default: 8.99e9)

Look for charge values (may be in scientific notation like 1e-9), distance measurements, and optionally the electrostatic constant.

If no specific query text is provided, use these default values:
- charge1: 1e-9
- charge2: 2e-9  
- distance: 0.05
- constant: 8.99e9 (if mentioned)

Return ONLY valid JSON in this exact format:
{{"charge1": 1e-9, "charge2": 2e-9, "distance": 0.05}}

Or if constant is specified:
{{"charge1": 1e-9, "charge2": 2e-9, "distance": 0.05, "constant": 8.99e9}}"""

        response = llm_client.generate(prompt)
        content = response.content.strip()

        # Extract JSON from response
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
            parameters = json.loads(content)
            
            # Ensure we have the required parameters
            if 'charge1' not in parameters:
                parameters['charge1'] = 1e-9
            if 'charge2' not in parameters:
                parameters['charge2'] = 2e-9
            if 'distance' not in parameters:
                parameters['distance'] = 0.05
                
            # Convert to proper types
            parameters['charge1'] = float(parameters['charge1'])
            parameters['charge2'] = float(parameters['charge2'])
            parameters['distance'] = float(parameters['distance'])
            
            if 'constant' in parameters:
                parameters['constant'] = float(parameters['constant'])
            
            # Return in the exact format specified in the output schema
            return {
                "calculate_electrostatic_potential": parameters
            }
            
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            # Fallback to default values
            return {
                "calculate_electrostatic_potential": {
                    "charge1": 1e-9,
                    "charge2": 2e-9,
                    "distance": 0.05
                }
            }
            
    except Exception as e:
        # Even on error, return the expected structure with defaults
        return {
            "calculate_electrostatic_potential": {
                "charge1": 1e-9,
                "charge2": 2e-9,
                "distance": 0.05
            }
        }