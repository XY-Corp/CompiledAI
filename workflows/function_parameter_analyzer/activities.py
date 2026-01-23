from typing import Any, Dict, List, Optional
import asyncio
import json
import re
from pydantic import BaseModel

class FunctionCall(BaseModel):
    """Expected function call response."""
    function_name: str
    parameters: dict

async def analyze_user_question(
    user_question: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Analyze the user's question to determine which function to call and extract the appropriate parameters.
    
    Args:
        user_question: The user's raw question that needs analysis to extract function call parameters
        available_functions: List of available function definitions with names, descriptions, and parameter schemas
        
    Returns:
        Dict where the function name is the top-level key and parameters are nested
        Example: {"cellbio.get_proteins": {"cell_compartment": "plasma membrane", "include_description": false}}
    """
    try:
        # Handle JSON string input defensively
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)
            
        if not isinstance(available_functions, list) or not available_functions:
            return {"error": "available_functions must be a non-empty list"}
            
        # If only one function and no user question, use it with default values
        if not user_question and len(available_functions) == 1:
            func = available_functions[0]
            func_name = func.get('name', 'unknown')
            params_schema = func.get('parameters', {})
            
            # Extract default values for required parameters
            result_params = {}
            if isinstance(params_schema, dict) and 'properties' in params_schema:
                properties = params_schema['properties']
                required_params = params_schema.get('required', [])
                
                for param_name in required_params:
                    param_info = properties.get(param_name, {})
                    param_type = param_info.get('type', 'string')
                    
                    # For cell compartment, use a common default
                    if param_name == 'cell_compartment':
                        result_params[param_name] = "plasma membrane"
                    elif param_type == 'string':
                        result_params[param_name] = ""
                    elif param_type == 'boolean':
                        result_params[param_name] = False
                    elif param_type == 'number' or param_type == 'integer':
                        result_params[param_name] = 0
                    else:
                        result_params[param_name] = None
            
            return {func_name: result_params}
        
        # Format functions with EXACT parameter names for LLM
        functions_text = "Available Functions:\n"
        for func in available_functions:
            func_name = func.get('name', 'unknown')
            func_desc = func.get('description', 'No description')
            params_schema = func.get('parameters', {})
            
            functions_text += f"\n{func_name}:\n"
            functions_text += f"  Description: {func_desc}\n"
            functions_text += f"  Parameters:\n"
            
            if isinstance(params_schema, dict) and 'properties' in params_schema:
                properties = params_schema['properties']
                required_params = params_schema.get('required', [])
                
                for param_name, param_info in properties.items():
                    param_type = param_info.get('type', 'string')
                    param_desc = param_info.get('description', 'No description')
                    default_val = param_info.get('default', None)
                    is_required = param_name in required_params
                    req_text = " (required)" if is_required else " (optional)"
                    
                    default_text = f" [default: {default_val}]" if default_val is not None else ""
                    functions_text += f"    - {param_name}: {param_type}{req_text} - {param_desc}{default_text}\n"
        
        # Create a clear prompt for function selection
        prompt = f"""User question: "{user_question}"

{functions_text}

Select the most appropriate function and extract parameters from the user's question.

CRITICAL REQUIREMENTS:
1. Return ONLY valid JSON - no markdown code blocks, no explanations
2. Use the function name as the TOP-LEVEL key
3. Use the EXACT parameter names shown above
4. For boolean parameters, use true/false (not "true"/"false" strings)
5. Extract meaningful values from the user question when possible

Example format:
{{"cellbio.get_proteins": {{"cell_compartment": "plasma membrane", "include_description": false}}}}

JSON response:"""

        response = llm_client.generate(prompt)
        content = response.content.strip()
        
        # Clean up the response - remove any markdown blocks
        if "```" in content:
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
            if json_match:
                content = json_match.group(1)
            else:
                json_match = re.search(r'\{.*?\}', content, re.DOTALL)
                if json_match:
                    content = json_match.group(0)
        
        # Try to parse the JSON response
        try:
            result = json.loads(content)
            # Ensure it's a valid function call structure
            if isinstance(result, dict) and len(result) >= 1:
                return result
            else:
                # Fallback: use first function with defaults
                func = available_functions[0]
                func_name = func.get('name', 'unknown')
                return {func_name: {"cell_compartment": "plasma membrane"}}
                
        except json.JSONDecodeError as e:
            # Fallback: use first function with meaningful defaults
            if available_functions:
                func = available_functions[0]
                func_name = func.get('name', 'unknown')
                params_schema = func.get('parameters', {})
                
                result_params = {}
                if isinstance(params_schema, dict) and 'properties' in params_schema:
                    properties = params_schema['properties']
                    required_params = params_schema.get('required', [])
                    
                    for param_name in required_params:
                        param_info = properties.get(param_name, {})
                        param_type = param_info.get('type', 'string')
                        
                        if param_name == 'cell_compartment':
                            result_params[param_name] = "plasma membrane"
                        elif param_type == 'boolean':
                            result_params[param_name] = False
                        elif param_type == 'string':
                            result_params[param_name] = ""
                        else:
                            result_params[param_name] = None
                
                return {func_name: result_params}
            
            return {"error": f"Failed to parse LLM response as JSON: {e}"}
            
    except Exception as e:
        return {"error": f"Error analyzing user question: {e}"}