from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel


class FunctionCall(BaseModel):
    """Model for a function call with parameters."""
    function: str
    parameters: dict


async def extract_function_parameters(
    user_query: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Analyzes the user's natural language query to identify which function to call and extract the required parameters.
    
    Args:
        user_query: The complete user query text that needs to be parsed
        available_functions: List of function definitions for context
        
    Returns:
        Dict with function name as key and parameters as nested object
    """
    try:
        # Handle JSON string input defensively
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)
        
        # Validate input
        if not isinstance(available_functions, list) or not available_functions:
            return {"error": "available_functions must be a non-empty list"}
        
        if not user_query or not user_query.strip():
            return {"error": "user_query cannot be empty"}
        
        # Format functions for LLM with exact parameter names
        functions_text = "Available Functions:\n"
        for func in available_functions:
            func_name = func.get('name', 'unknown')
            func_desc = func.get('description', '')
            
            # Get parameters schema (check both 'parameters' and 'params' keys)
            params_schema = func.get('parameters', func.get('params', {}))
            
            functions_text += f"Function: {func_name}\n"
            functions_text += f"Description: {func_desc}\n"
            
            # Extract parameter details
            if params_schema:
                properties = params_schema.get('properties', {})
                required = params_schema.get('required', [])
                
                functions_text += "Parameters:\n"
                for param_name, param_info in properties.items():
                    param_type = param_info.get('type', 'string')
                    param_desc = param_info.get('description', '')
                    req_status = " (required)" if param_name in required else " (optional)"
                    functions_text += f"  - {param_name}: {param_type}{req_status} - {param_desc}\n"
            
            functions_text += "\n"
        
        # Create prompt for LLM to extract function call
        prompt = f"""User Query: "{user_query}"

{functions_text}

Analyze the user query and determine:
1. Which function should be called
2. What parameter values to extract from the query

Extract parameter values directly from the user's query. If a required parameter cannot be determined from the query, use reasonable defaults based on context.

Return ONLY valid JSON in this exact format:
{{"function": "function_name", "parameters": {{"param_name": "extracted_value"}}}}

Example:
{{"function": "population_projections", "parameters": {{"country": "United States", "years": 20}}}}"""

        # Use LLM to analyze the query
        response = llm_client.generate(prompt)
        content = response.content.strip()
        
        # Extract JSON from response (handle markdown code blocks)
        if "```" in content:
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
            if json_match:
                content = json_match.group(1)
            else:
                json_match = re.search(r'\{.*?\}', content, re.DOTALL)
                if json_match:
                    content = json_match.group(0)
        
        # Parse and validate the LLM response
        try:
            parsed_response = json.loads(content)
            validated = FunctionCall(**parsed_response)
            
            # Return in the required format: function name as key, parameters as value
            function_name = validated.function
            return {function_name: validated.parameters}
            
        except (json.JSONDecodeError, ValueError) as e:
            # Fallback: try to extract basic information using patterns
            return _fallback_extraction(user_query, available_functions)
            
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}


def _fallback_extraction(user_query: str, available_functions: list) -> dict[str, Any]:
    """Fallback extraction using simple patterns when LLM parsing fails."""
    try:
        # Simple fallback - take first function and extract basic parameters
        if not available_functions:
            return {"error": "No functions available"}
        
        first_func = available_functions[0]
        func_name = first_func.get('name', 'unknown')
        
        # Extract basic parameters using simple patterns
        params = {}
        params_schema = first_func.get('parameters', {}).get('properties', {})
        
        for param_name, param_info in params_schema.items():
            param_type = param_info.get('type', 'string')
            
            # Simple extraction patterns
            if param_type == 'string':
                # Extract quoted strings or common country names
                if 'country' in param_name.lower():
                    country_match = re.search(r'\b(?:United States|USA|China|India|Brazil|Russia)\b', user_query, re.IGNORECASE)
                    if country_match:
                        params[param_name] = country_match.group(0)
                    else:
                        params[param_name] = "United States"  # Default
            elif param_type == 'integer':
                # Extract numbers
                number_match = re.search(r'\b(\d+)\b', user_query)
                if number_match:
                    params[param_name] = int(number_match.group(1))
                else:
                    params[param_name] = 10  # Default
            elif param_type == 'float':
                # Extract decimal numbers
                float_match = re.search(r'\b(\d+\.?\d*)\b', user_query)
                if float_match:
                    params[param_name] = float(float_match.group(1))
                else:
                    params[param_name] = 1.0  # Default
        
        return {func_name: params}
        
    except Exception:
        return {"error": "Fallback extraction failed"}