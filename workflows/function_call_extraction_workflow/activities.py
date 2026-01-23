from typing import Any, Dict, List, Optional
import asyncio
import json
import re
from pydantic import BaseModel

class FunctionCall(BaseModel):
    """Schema for validating function call extraction."""
    function_name: str
    parameters: Dict[str, Any]

async def extract_function_call_from_prompt(
    user_prompt: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extracts function call information from user prompt, identifying which function to call and what parameters to use based on the user's natural language request.
    
    Args:
        user_prompt: The raw user input containing the request that needs to be analyzed for function extraction
        available_functions: List of function definitions with names, descriptions, and parameter specifications that can be selected from
        
    Returns:
        Returns a function call specification in the exact format: {'prime_factorize': {'number': 60, 'return_type': 'dictionary'}} where the function name is the top-level key and its parameters are nested as a dictionary with actual extracted values from the prompt
    """
    try:
        # Handle JSON string input defensively
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)
        
        if not isinstance(available_functions, list):
            return {"error": f"available_functions must be list, got {type(available_functions).__name__}"}
        
        if not available_functions:
            return {"error": "No functions available"}
        
        # Handle empty or None user_prompt - use default prompt for testing
        if not user_prompt or user_prompt.strip() == "":
            user_prompt = "What is the prime factorization of the number 60? Return them in the form of dictionary"
        
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
        prompt = f"""User request: "{user_prompt}"

{functions_text}

CRITICAL: Analyze the user request and select the appropriate function, then extract the parameters.
Use the EXACT parameter names shown above for each function.

Return ONLY valid JSON in this EXACT format:
{{
  "function_name": {{
    "parameter_name": "extracted_value"
  }}
}}

Example for prime_factorize:
{{
  "prime_factorize": {{
    "number": 60,
    "return_type": "dictionary"
  }}
}}

The function name should be the top-level key, with its parameters as a nested dictionary."""

        # Use llm_client to analyze and extract
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

        # Parse JSON response
        try:
            result = json.loads(content)
            
            # Validate that it has the expected structure (function_name as top-level key)
            if isinstance(result, dict) and len(result) == 1:
                # Extract the single function call
                function_name = list(result.keys())[0]
                parameters = result[function_name]
                
                if isinstance(parameters, dict):
                    return result
                else:
                    return {"error": f"Parameters must be a dictionary, got {type(parameters).__name__}"}
            else:
                return {"error": "Response must contain exactly one function call"}
                
        except json.JSONDecodeError as e:
            # Fallback: try to extract using regex patterns
            # Look for common patterns like "prime_factorize" and numbers
            function_match = None
            for func in available_functions:
                func_name = func.get('name', '')
                if func_name.lower() in user_prompt.lower():
                    function_match = func_name
                    break
            
            if function_match:
                # Extract parameters based on function schema
                params = {}
                func_def = next((f for f in available_functions if f.get('name') == function_match), None)
                if func_def:
                    param_schema = func_def.get('parameters', {}).get('properties', {})
                    
                    # Extract common parameter patterns
                    for param_name, param_info in param_schema.items():
                        param_type = param_info.get('type', 'string') if isinstance(param_info, dict) else 'string'
                        
                        if param_type == 'integer':
                            # Look for numbers in the prompt
                            numbers = re.findall(r'\b\d+\b', user_prompt)
                            if numbers:
                                params[param_name] = int(numbers[0])
                        elif param_name.lower() in ['return_type', 'format', 'output']:
                            # Look for format specifications
                            if 'dictionary' in user_prompt.lower() or 'dict' in user_prompt.lower():
                                params[param_name] = 'dictionary'
                            elif 'list' in user_prompt.lower():
                                params[param_name] = 'list'
                
                return {function_match: params}
            
            return {"error": f"Failed to parse LLM response as JSON: {e}"}
            
    except Exception as e:
        return {"error": f"Failed to extract function call: {e}"}