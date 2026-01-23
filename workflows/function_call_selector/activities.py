from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel


class FunctionCallResult(BaseModel):
    """Model for validating LLM response structure."""
    function_name: str
    parameters: Dict[str, Any]


async def extract_function_call(
    prompt: str,
    functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Analyzes the user's natural language prompt against available functions and extracts the function name and its parameters.
    
    Uses LLM to understand user intent and map it to the correct function with properly typed parameters.
    
    Args:
        prompt: The natural language user request describing what operation they want to perform
        functions: List of available function definitions, each containing name, description, and parameters schema
        
    Returns:
        A function call object with the function name as the top-level key and parameters as nested object.
        Example: {"calculus.derivative": {"function": "2x^2", "value": 1, "function_variable": "x"}}
    """
    try:
        # Handle JSON string input defensively
        if isinstance(functions, str):
            functions = json.loads(functions)
        
        if not isinstance(functions, list):
            return {"error": f"functions must be list, got {type(functions).__name__}"}
        
        if not functions:
            return {"error": "No functions available"}
        
        # Handle empty or None prompt
        if not prompt or (isinstance(prompt, str) and prompt.strip() == ""):
            return {"error": "Prompt is required"}
        
        # Build function descriptions for the LLM with EXACT parameter names
        functions_text = "Available Functions:\n"
        function_param_map = {}
        
        for func in functions:
            func_name = func.get('name', 'unknown')
            func_desc = func.get('description', 'No description')
            
            # Handle parameters schema - check both 'parameters' and 'params' keys
            params_schema = func.get('parameters', func.get('params', {}))
            
            functions_text += f"\n**{func_name}**: {func_desc}\n"
            
            param_types = {}
            
            # Extract parameter details with exact names and types
            if isinstance(params_schema, dict):
                # Handle both direct properties and nested properties
                properties = params_schema.get('properties', {})
                required = params_schema.get('required', [])
                
                # If no properties found, try treating the schema itself as properties
                if not properties and 'type' not in params_schema:
                    properties = params_schema
                
                if properties:
                    functions_text += "  Parameters (use EXACT names):\n"
                    for param_name, param_info in properties.items():
                        if param_name in ('type', 'required', 'properties'):
                            continue
                            
                        if isinstance(param_info, dict):
                            param_type = param_info.get('type', 'string')
                            param_desc = param_info.get('description', '')
                        else:
                            param_type = str(param_info)
                            param_desc = ''
                        
                        required_marker = " (required)" if param_name in required else ""
                        functions_text += f"    - \"{param_name}\": {param_type}{required_marker} - {param_desc}\n"
                        param_types[param_name] = param_type
            
            function_param_map[func_name] = param_types
        
        # Create clean prompt asking for the exact format required
        llm_prompt = f"""Analyze this user request and extract the function call parameters.

User Request: "{prompt}"

{functions_text}

Your task:
1. Identify which function best matches the user's intent
2. Extract the parameter values from the user's request
3. Return a JSON object with the function name as the top-level key

CRITICAL INSTRUCTIONS:
- Use the EXACT parameter names shown above (case-sensitive)
- For mathematical expressions, convert common notation to Python syntax (e.g., "2x^2" becomes "2x**2")
- For numeric values, return them as numbers (not strings)
- For string values, return them as strings

Return ONLY a JSON object in this exact format:
{{"function_name": {{"param1": value1, "param2": value2}}}}

For example, if the user wants to compute a derivative:
{{"calculus.derivative": {{"function": "2x**2", "value": 1, "function_variable": "x"}}}}

JSON response:"""

        # Call LLM to extract function and parameters
        response = llm_client.generate(llm_prompt)
        content = response.content.strip()
        
        # Extract JSON from response (handles markdown code blocks)
        if "```" in content:
            # Extract content between ```json and ``` or between ``` and ```
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
            if json_match:
                content = json_match.group(1)
            else:
                # Try to find any JSON object
                json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', content, re.DOTALL)
                if json_match:
                    content = json_match.group(0)
        else:
            # Try to find JSON object in content
            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', content, re.DOTALL)
            if json_match:
                content = json_match.group(0)
        
        # Parse the JSON response
        parsed = json.loads(content)
        
        # Validate structure - should have function name as top-level key
        if not isinstance(parsed, dict) or len(parsed) == 0:
            return {"error": "Invalid response structure from LLM"}
        
        # Get the function name (first key) and parameters
        func_name = list(parsed.keys())[0]
        params = parsed[func_name]
        
        # Type coercion based on function schema
        if func_name in function_param_map:
            expected_types = function_param_map[func_name]
            for param_name, param_value in params.items():
                if param_name in expected_types:
                    expected_type = expected_types[param_name]
                    # Coerce types as needed
                    if expected_type in ('integer', 'int') and not isinstance(param_value, int):
                        try:
                            params[param_name] = int(param_value)
                        except (ValueError, TypeError):
                            pass
                    elif expected_type in ('number', 'float') and not isinstance(param_value, (int, float)):
                        try:
                            params[param_name] = float(param_value)
                        except (ValueError, TypeError):
                            pass
                    elif expected_type == 'string' and not isinstance(param_value, str):
                        params[param_name] = str(param_value)
        
        # Return in the expected format: {"function_name": {"param": value}}
        return {func_name: params}
        
    except json.JSONDecodeError as e:
        return {"error": f"Failed to parse LLM response as JSON: {e}"}
    except Exception as e:
        return {"error": f"Failed to extract function call: {str(e)}"}
