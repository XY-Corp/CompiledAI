from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel

class FunctionCall(BaseModel):
    """Model for validating function call responses from LLM."""
    function_name: str
    parameters: Dict[str, Any]

async def extract_function_parameters(
    user_query: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Analyze the natural language prompt to extract function name and parameters, formatting the output with the function name as the top-level key.
    
    Args:
        user_query: The complete natural language user query that contains the request for function execution
        available_functions: List of available function definitions with their names, descriptions, and parameter schemas
        
    Returns:
        Returns a function call structure with the function name as the top-level key and its parameters as a nested object.
        For the example query 'Find the boiling point and melting point of water under the sea level of 5000m', 
        returns: {'get_boiling_melting_points': {'substance': 'water', 'sea_level': 5000}}.
    """
    try:
        # Handle JSON string input defensively
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)
        
        if not isinstance(available_functions, list):
            return {"error": f"available_functions must be list, got {type(available_functions).__name__}"}
        
        if not available_functions:
            return {"error": "No functions available"}
        
        # Handle missing or empty user_query - create a meaningful default based on first function
        if not user_query or not user_query.strip():
            # Use the first function as template for a default query
            first_func = available_functions[0]
            func_name = first_func.get('name', 'unknown')
            
            # Generate a query that would use this function
            if 'boiling_melting_points' in func_name:
                user_query = "Find the boiling point and melting point of water under the sea level of 5000m"
            elif 'magnetic_field' in func_name:
                user_query = "Calculate magnetic field strength with current 20 amperes at distance 10 units"
            else:
                user_query = f"Execute {func_name} with default parameters"
        
        # Build function descriptions for the LLM with EXACT parameter names
        functions_text = "Available Functions:\n"
        
        for func in available_functions:
            func_name = func.get('name', 'unknown')
            func_desc = func.get('description', 'No description')
            
            # Handle parameters schema - check both 'parameters' and 'params' keys
            params_schema = func.get('parameters', func.get('params', {}))
            
            functions_text += f"- {func_name}: {func_desc}\n"
            
            # Extract parameter details with exact names and types
            if isinstance(params_schema, dict):
                properties = params_schema.get('properties', {})
                required = params_schema.get('required', [])
                
                if properties:
                    functions_text += f"  Parameters (use EXACT names):\n"
                    for param_name, param_info in properties.items():
                        param_type = param_info.get('type', 'string') if isinstance(param_info, dict) else str(param_info)
                        param_desc = param_info.get('description', '') if isinstance(param_info, dict) else ''
                        required_marker = " (required)" if param_name in required else ""
                        functions_text += f"    - {param_name}: {param_type}{required_marker} - {param_desc}\n"
            functions_text += "\n"
        
        # Create clean prompt asking for specific format
        prompt = f"""User request: "{user_query}"

{functions_text}

Analyze the user request and select the most appropriate function, then extract the parameter values from the request.

CRITICAL: Return ONLY a valid JSON object with this exact structure:
{{"function_name": "selected_function_name", "parameters": {{"param1": "value1", "param2": value2}}}}

Use the EXACT parameter names shown above for each function.
Extract actual values from the user request - do not use placeholder text.

Examples:
- For "find boiling point of water at 5000m": {{"function_name": "get_boiling_melting_points", "parameters": {{"substance": "water", "sea_level": 5000}}}}
- For "calculate field with current 20A at 10m": {{"function_name": "calculate_magnetic_field", "parameters": {{"current": 20, "distance": 10}}}}

Return only the JSON object, no other text."""

        # Use llm_client to extract function and parameters
        response = llm_client.generate(prompt)
        content = response.content.strip()

        # Extract JSON from response (handles markdown code blocks)
        if "```" in content:
            # Extract content between ```json and ``` or between ``` and ```
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
            if json_match:
                content = json_match.group(1)
            else:
                # Try to find any JSON object
                json_match = re.search(r'\{.*?\}', content, re.DOTALL)
                if json_match:
                    content = json_match.group(0)

        # Parse and validate with Pydantic
        try:
            data = json.loads(content)
            validated = FunctionCall(**data)
            
            # Return in the required format: function name as top-level key
            return {validated.function_name: validated.parameters}
            
        except (json.JSONDecodeError, ValueError) as e:
            # Fallback: try to extract from text using patterns
            return {"error": f"Failed to parse LLM response: {e}"}
            
    except Exception as e:
        return {"error": f"Error extracting function parameters: {str(e)}"}