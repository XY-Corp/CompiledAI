from typing import Any, Dict, List, Optional
import asyncio
import json
import re
from pydantic import BaseModel


async def extract_function_call(
    prompt: str,
    functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Analyzes the user prompt against available functions to determine which function should be called and extracts the parameter values from the prompt.
    
    Returns the function name as the top-level key with a nested object containing the extracted parameters.
    
    Args:
        prompt: The natural language user request that needs to be parsed to identify the function to call and extract parameter values
        functions: List of available function definitions, each containing name, description, and parameters schema with required fields
        
    Returns:
        Dict with the function name as the top-level key and its parameters as a nested object.
        Example: {"math.hcf": {"number1": 36, "number2": 24}}
    """
    try:
        # Parse JSON strings if needed
        if isinstance(functions, str):
            functions = json.loads(functions)
        
        # Validate types
        if not isinstance(functions, list):
            return {"error": f"functions must be list, got {type(functions).__name__}"}
        
        if not functions:
            return {"error": "No functions available"}
        
        if not prompt or (isinstance(prompt, str) and prompt.strip() == ""):
            return {"error": "Empty prompt provided"}
        
        # Build function descriptions for the LLM with EXACT parameter names
        functions_text = "Available Functions:\n"
        
        for func in functions:
            func_name = func.get('name', 'unknown')
            func_desc = func.get('description', 'No description')
            
            # Handle parameters schema - check both 'parameters' and 'params' keys
            params_schema = func.get('parameters', func.get('params', {}))
            
            functions_text += f"\n**{func_name}**: {func_desc}\n"
            
            # Extract parameter details with exact names and types
            if isinstance(params_schema, dict):
                # Handle both direct properties and nested structure
                properties = params_schema.get('properties', {})
                if not properties and params_schema.get('type') == 'dict':
                    properties = params_schema.get('properties', {})
                
                required = params_schema.get('required', [])
                
                if properties:
                    functions_text += "  Parameters (use EXACT names):\n"
                    for param_name, param_info in properties.items():
                        if isinstance(param_info, dict):
                            param_type = param_info.get('type', 'string')
                            param_desc = param_info.get('description', '')
                        else:
                            param_type = str(param_info)
                            param_desc = ''
                        
                        required_marker = " (required)" if param_name in required else " (optional)"
                        functions_text += f"    - \"{param_name}\": {param_type}{required_marker} - {param_desc}\n"
        
        # Create clean prompt asking for the exact format required
        llm_prompt = f"""Analyze this user request and determine which function to call with what parameters.

User Request: "{prompt}"

{functions_text}

INSTRUCTIONS:
1. Identify which function best matches the user's intent
2. Extract the parameter values from the user's request
3. Use the EXACT parameter names shown above for the selected function
4. Convert values to the appropriate types (numbers should be integers/floats, not strings)

Return ONLY a JSON object with the function name as the top-level key and parameters as a nested object.

Example format:
{{"function_name": {{"param1": value1, "param2": value2}}}}

For instance, if user says "find HCF of 36 and 24" and math.hcf function has parameters number1 and number2:
{{"math.hcf": {{"number1": 36, "number2": 24}}}}

Return ONLY the JSON, no explanation."""

        # Use llm_client to analyze and extract
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
        
        # Validate that result has expected structure (function name as key with params as nested object)
        if not isinstance(result, dict):
            return {"error": f"Expected dict, got {type(result).__name__}"}
        
        # Return the result directly - it should be in format {"function_name": {"param": value}}
        return result
        
    except json.JSONDecodeError as e:
        return {"error": f"Invalid JSON in LLM response: {e}"}
    except Exception as e:
        return {"error": f"Failed to extract function call: {str(e)}"}
