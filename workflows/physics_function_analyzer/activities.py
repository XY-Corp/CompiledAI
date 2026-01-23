from typing import Any, Dict, List, Optional
import asyncio
import json
import re
from pydantic import BaseModel

class FunctionCall(BaseModel):
    """Expected structure for function call extraction."""
    function_name: str
    parameters: Dict[str, Any]

async def parse_physics_problem(
    problem_text: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Parse physics problem text and extract numerical parameters and values needed for electric field calculation.
    
    Analyzes natural language physics problem descriptions and maps them to appropriate
    calculation functions with extracted parameter values.
    
    Args:
        problem_text: Natural language physics problem description containing charge values, 
                     distances, and other physical parameters
        available_functions: List of available physics calculation functions with their parameter specifications
        
    Returns:
        Function call object with the function name as the top-level key and its parameters 
        as a nested object. For electric field calculations, returns: 
        {"calculate_electric_field": {"charge": 2, "distance": 3, "permitivity": 8.854e-12}}
    """
    try:
        # Handle JSON string input defensively
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)
        
        if not isinstance(available_functions, list):
            return {"error": f"available_functions must be list, got {type(available_functions).__name__}"}
        
        # Format available functions with exact parameter names for LLM
        functions_text = "Available Physics Functions:\n"
        for func in available_functions:
            # Get parameter schema - handle both 'parameters' and 'params' keys
            params_schema = func.get('parameters', func.get('params', {}))
            
            # Extract parameter details
            param_details = []
            if isinstance(params_schema, dict):
                # Handle nested schema structure
                if 'type' in params_schema and params_schema['type'] == 'object':
                    properties = params_schema.get('properties', {})
                    for param_name, param_info in properties.items():
                        param_type = param_info.get('type', 'string')
                        param_details.append(f'"{param_name}": <{param_type}>')
                else:
                    # Direct parameter mapping
                    for param_name, param_info in params_schema.items():
                        if isinstance(param_info, str):
                            param_type = param_info
                        else:
                            param_type = param_info.get('type', 'string')
                        param_details.append(f'"{param_name}": <{param_type}>')
            
            function_description = func.get('description', 'No description')
            functions_text += f"- {func['name']}: {function_description}\n"
            if param_details:
                functions_text += f"  Parameters: {{{', '.join(param_details)}}}\n"
        
        # Create prompt for LLM to extract parameters
        prompt = f"""Physics Problem: "{problem_text}"

{functions_text}

Analyze the physics problem and:
1. Identify which function is most appropriate for solving this problem
2. Extract the numerical values and parameters needed from the problem text
3. Map them to the exact parameter names required by the selected function

CRITICAL: Use the EXACT parameter names shown above for the selected function.

For electric field calculations, common parameter mappings:
- charge: Extract charge value in Coulombs (C) 
- distance: Extract distance value in meters (m)
- permitivity: Use vacuum permitivity 8.854e-12 F/m if not specified

Return ONLY valid JSON in this format:
{{"function_name": {{"exact_param_name1": value1, "exact_param_name2": value2}}}}

Example: {{"calculate_electric_field": {{"charge": 2, "distance": 3, "permitivity": 8.854e-12}}}}"""

        # Use LLM to extract function and parameters
        response = llm_client.generate(prompt)
        content = response.content.strip()
        
        # Extract JSON from response (handle markdown code blocks)
        if "```" in content:
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
            if json_match:
                content = json_match.group(1)
            else:
                # Try to find any JSON object
                json_match = re.search(r'\{.*?\}', content, re.DOTALL)
                if json_match:
                    content = json_match.group(0)
        
        # Parse JSON response
        try:
            function_call_data = json.loads(content)
            
            # Validate that it's a single function call with parameters
            if not isinstance(function_call_data, dict) or len(function_call_data) != 1:
                return {"error": "Expected single function call object"}
            
            # Return the function call in the required format
            return function_call_data
            
        except json.JSONDecodeError as e:
            # Fallback: try to extract values with regex for electric field
            charge_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:coulombs?|C)\b', problem_text, re.IGNORECASE)
            distance_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:meters?|m)\b', problem_text, re.IGNORECASE)
            
            if charge_match and distance_match:
                charge = float(charge_match.group(1))
                distance = float(distance_match.group(1))
                
                return {
                    "calculate_electric_field": {
                        "charge": int(charge) if charge.is_integer() else charge,
                        "distance": int(distance) if distance.is_integer() else distance,
                        "permitivity": 8.854e-12
                    }
                }
            
            return {"error": f"Failed to parse LLM response: {e}"}
            
    except Exception as e:
        return {"error": f"Error processing physics problem: {e}"}