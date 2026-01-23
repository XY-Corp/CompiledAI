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
    """Parses the user prompt against available function definitions to determine which function to call and extracts all required/optional parameters.
    
    Uses LLM to understand natural language intent and map it to function parameters.
    
    Args:
        prompt: The natural language user request describing what calculation or operation they want to perform
        functions: List of available function definitions, each containing name, description, and parameters schema
        
    Returns:
        Returns a function call object with the function name as the top-level key and parameters as a nested object.
        Example: {"integrate": {"function": "x^3", "start_x": -2, "end_x": 3, "method": "simpson"}}
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
                # Handle both direct properties and nested 'properties' key
                if 'properties' in params_schema:
                    properties = params_schema.get('properties', {})
                    required = params_schema.get('required', [])
                elif params_schema.get('type') == 'dict':
                    # Handle schema format where type is 'dict' and properties are nested
                    properties = params_schema.get('properties', {})
                    required = params_schema.get('required', [])
                else:
                    # Assume direct parameter definitions
                    properties = params_schema
                    required = []
                
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
                        
                        required_marker = " (required)" if param_name in required else ""
                        if param_default is not None and param_name not in required:
                            required_marker = f" (optional, default: {param_default})"
                        
                        enum_text = f", allowed values: {param_enum}" if param_enum else ""
                        functions_text += f"    - \"{param_name}\": {param_type}{required_marker} - {param_desc}{enum_text}\n"
                        
                        param_types[param_name] = param_type
            
            function_param_map[func_name] = param_types
        
        # Create clean prompt asking for the exact format required
        llm_prompt = f"""Analyze this user request and extract the function call parameters.

User Request: "{prompt}"

{functions_text}

INSTRUCTIONS:
1. Select the most appropriate function from the available options based on the user's intent
2. Extract all parameter values from the user request
3. Use EXACT parameter names as shown above
4. Convert numerical values to appropriate types (integers for integer params)
5. For mathematical expressions like "x^3", use Python notation "x**3"

Return ONLY a valid JSON object in this exact format:
{{"function_name": {{"param1": value1, "param2": value2, ...}}}}

Where "function_name" is replaced with the actual function name, and parameters use their exact names.

Example for integrate function:
{{"integrate": {{"function": "x**3", "start_x": -2, "end_x": 3, "method": "simpson"}}}}

Return ONLY the JSON object, no explanation or markdown."""

        # Use LLM client to extract the function call
        response = llm_client.generate(llm_prompt)
        
        # Extract JSON from response
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
            return {"error": "Invalid response structure from LLM"}
        
        # Return the function call object directly
        return result
        
    except json.JSONDecodeError as e:
        return {"error": f"Failed to parse LLM response as JSON: {e}"}
    except Exception as e:
        return {"error": f"Error extracting function call: {str(e)}"}
