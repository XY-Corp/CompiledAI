from typing import Any, Dict, List, Optional
import asyncio
import json
import re


async def extract_function_call(
    prompt: str,
    functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Parse the user's natural language prompt to identify which function to call and extract the required parameters.
    
    Analyzes the prompt against the available function definitions to select the appropriate function
    (calculate_area_under_curve) and extracts parameters like the mathematical function expression,
    interval bounds, and optional method.
    
    Args:
        prompt: The user's natural language request describing what calculation they want to perform
        functions: List of available function definitions with their names, descriptions, and parameter schemas
        
    Returns:
        A function call object with the function name as the top-level key and parameters as nested object.
        Example: {"calculate_area_under_curve": {"function": "x^2", "interval": [1.0, 3.0], "method": "trapezoidal"}}
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
            return {"error": "No prompt provided"}
        
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
                properties = params_schema.get('properties', {})
                required = params_schema.get('required', [])
                
                if properties:
                    functions_text += "  Parameters (use EXACT names):\n"
                    for param_name, param_info in properties.items():
                        if isinstance(param_info, dict):
                            param_type = param_info.get('type', 'string')
                            param_desc = param_info.get('description', '')
                            param_default = param_info.get('default', None)
                            param_enum = param_info.get('enum', None)
                        else:
                            param_type = str(param_info)
                            param_desc = ''
                            param_default = None
                            param_enum = None
                        
                        required_marker = " (required)" if param_name in required else f" (optional, default: {param_default})"
                        enum_text = f", allowed values: {param_enum}" if param_enum else ""
                        functions_text += f"    - \"{param_name}\": {param_type}{required_marker} - {param_desc}{enum_text}\n"
                        
                        param_types[param_name] = param_type
            
            function_param_map[func_name] = param_types
        
        # Create clean prompt asking for the exact format required
        llm_prompt = f"""Analyze this user request and extract the function call parameters.

User Request: "{prompt}"

{functions_text}

INSTRUCTIONS:
1. Select the most appropriate function based on the user's request
2. Extract ALL parameter values from the user's request
3. Use EXACT parameter names as shown above
4. For mathematical expressions, convert common notations:
   - "y=x^2" or "x^2" should be "x**2" (Python syntax)
   - "x squared" should be "x**2"
   - "sin(x)" stays as "sin(x)"
5. For intervals like "from x=1 to x=3" or "from 1 to 3", extract as [1.0, 3.0]
6. If method is not specified, omit it from the output (default will be used)

Return ONLY valid JSON in this exact format (function name as top-level key):
{{"function_name": {{"param1": value1, "param2": value2}}}}

Example for calculate_area_under_curve:
{{"calculate_area_under_curve": {{"function": "x**2", "interval": [1.0, 3.0]}}}}
or with method:
{{"calculate_area_under_curve": {{"function": "x**2", "interval": [1.0, 3.0], "method": "simpson"}}}}

Return ONLY the JSON, no explanation."""

        # Call LLM (synchronous - do NOT await)
        response = llm_client.generate(llm_prompt)
        
        content = response.content.strip()
        
        # Remove markdown code blocks if present
        if "```" in content:
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
            if json_match:
                content = json_match.group(1)
            else:
                # Try to find any JSON object
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    content = json_match.group(0)
        
        # Parse the JSON response
        result = json.loads(content)
        
        # Validate that result has the expected structure (function name as top-level key)
        if not isinstance(result, dict):
            return {"error": f"Expected dict, got {type(result).__name__}"}
        
        # Ensure interval values are floats if present
        for func_name, params in result.items():
            if isinstance(params, dict) and 'interval' in params:
                interval = params['interval']
                if isinstance(interval, list) and len(interval) == 2:
                    params['interval'] = [float(interval[0]), float(interval[1])]
        
        return result
        
    except json.JSONDecodeError as e:
        return {"error": f"Failed to parse LLM response as JSON: {e}"}
    except Exception as e:
        return {"error": f"Failed to extract function call: {str(e)}"}
