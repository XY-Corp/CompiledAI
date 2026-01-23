from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel


class FunctionCall(BaseModel):
    """Represents a function call with parameters."""
    function_name: str
    parameters: Dict[str, Any]


async def parse_function_call_request(
    query_text: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Parse natural language query to extract function name and parameter values for function calling.
    
    Args:
        query_text: The natural language query containing the function call request and parameter values to extract
        available_functions: List of available function definitions with their parameters and descriptions for context
        
    Returns:
        Returns a single function call with the function name as the top-level key and its parameters as a nested object.
    """
    try:
        # Handle JSON string input defensively
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)
        
        if not isinstance(available_functions, list):
            return {"error": f"available_functions must be list, got {type(available_functions).__name__}"}
        
        if not available_functions:
            return {"error": "No functions available"}
        
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
        prompt = f"""User query: "{query_text}"

{functions_text}

Parse this user query to identify which function to call and extract the parameter values.

CRITICAL REQUIREMENTS:
1. Use the EXACT parameter names shown above for each function
2. Extract actual parameter values from the user query
3. Return valid JSON in this exact format: {{"function_name": {{"param1": "value1", "param2": "value2"}}}}

For example, if the user says "solve the equation x²+3x+2=0" and we have solve_quadratic with parameters a, b, c:
{{"solve_quadratic": {{"a": 1, "b": 3, "c": 2}}}}

Return ONLY the JSON object with the function name as key and parameters as nested object:"""
        
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
        
        # Parse the JSON response
        try:
            result = json.loads(content)
            
            # Validate that it has the correct structure (function_name -> parameters)
            if isinstance(result, dict) and len(result) == 1:
                function_name = list(result.keys())[0]
                parameters = result[function_name]
                
                # Check if this function exists in available functions
                available_function_names = [f.get('name', '') for f in available_functions]
                if function_name in available_function_names:
                    return result
                else:
                    return {"error": f"Unknown function: {function_name}. Available: {available_function_names}"}
            else:
                return {"error": "Invalid response format from LLM"}
                
        except json.JSONDecodeError as e:
            # Try to extract JSON with regex as fallback
            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', content)
            if json_match:
                try:
                    result = json.loads(json_match.group(0))
                    return result
                except:
                    pass
            
            return {"error": f"Failed to parse LLM response as JSON: {e}"}
            
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}