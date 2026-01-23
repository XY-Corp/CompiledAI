from typing import Any, Dict, List, Optional
import asyncio
import json
import re
from pydantic import BaseModel


class QuadraticParams(BaseModel):
    """Pydantic model for quadratic equation parameters."""
    a: int
    b: int
    c: int


async def extract_function_call(
    prompt: str,
    functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Analyzes the user prompt and available functions to determine which function to call and extract the required parameters.
    
    Uses LLM to understand natural language and map it to function parameters.
    
    Args:
        prompt: The natural language user request containing the quadratic equation problem and coefficients to extract
        functions: List of available function definitions with names, descriptions, and parameter schemas to match against
        
    Returns:
        Returns a function call object with the function name as the top-level key and parameters as nested object.
        Example: {"algebra.quadratic_roots": {"a": 1, "b": -3, "c": 2}}
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
        llm_prompt = f"""Analyze this user request and extract the function call parameters.

User Request: "{prompt}"

{functions_text}

Your task:
1. Identify which function the user wants to call based on their request
2. Extract the parameter values from the user's request
3. For quadratic equations, identify coefficients a (x^2 term), b (x term), and c (constant term)

CRITICAL: Return ONLY valid JSON in this exact format:
{{"function_name": {{"param1": value, "param2": value}}}}

For quadratic equations like "x^2 - 3x + 2", the coefficients are:
- a = 1 (coefficient of x^2)
- b = -3 (coefficient of x, note the sign!)
- c = 2 (constant term)

Return ONLY the JSON object, no explanation."""

        # Use llm_client to analyze the prompt
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
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    content = json_match.group(0)
        
        # Parse the JSON response
        try:
            result = json.loads(content)
        except json.JSONDecodeError:
            # Try to find JSON object in the content
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group(0))
            else:
                return {"error": f"Failed to parse LLM response as JSON: {content}"}
        
        # Validate the result structure - should have function name as top-level key
        if not isinstance(result, dict):
            return {"error": f"Expected dict result, got {type(result).__name__}"}
        
        # Check if result has expected structure (function name as key with params as value)
        if len(result) == 0:
            return {"error": "No function call extracted from prompt"}
        
        # Get the function name (first key)
        func_name = list(result.keys())[0]
        params = result[func_name]
        
        # If the function is algebra.quadratic_roots, validate and ensure integer types
        if func_name == "algebra.quadratic_roots":
            try:
                validated_params = QuadraticParams(
                    a=int(params.get('a', 0)),
                    b=int(params.get('b', 0)),
                    c=int(params.get('c', 0))
                )
                return {func_name: validated_params.model_dump()}
            except (ValueError, TypeError) as e:
                return {"error": f"Invalid quadratic parameters: {e}"}
        
        # Return the extracted function call
        return result
        
    except json.JSONDecodeError as e:
        return {"error": f"Invalid JSON in functions: {e}"}
    except Exception as e:
        return {"error": f"Error extracting function call: {str(e)}"}
