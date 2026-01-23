from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel

class FunctionCall(BaseModel):
    """Structure for LLM function call response."""
    function: str
    parameters: Dict[str, Any]

async def analyze_prompt_for_function_selection(
    user_prompt: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Analyzes the user prompt to determine which function to call and extract the required parameters.
    
    Args:
        user_prompt: The raw user input containing the request that needs to be analyzed for function selection
        available_functions: List of available functions with their names, descriptions, and parameter specifications
        
    Returns:
        Function call structure with the function name as key and parameters as nested object.
    """
    try:
        # Handle JSON string input defensively
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)
        
        if not isinstance(available_functions, list):
            return {"error": f"available_functions must be list, got {type(available_functions).__name__}"}
        
        if not available_functions:
            return {"error": "No functions provided"}
        
        # Format functions with EXACT parameter names for the LLM
        functions_text = "Available Functions:\n"
        for func in available_functions:
            func_name = func.get('name', '')
            func_desc = func.get('description', '')
            
            # Handle parameters structure - check both 'parameters' and 'params' keys
            params_schema = func.get('parameters', func.get('params', {}))
            
            # Extract parameter details
            param_details = []
            required_params = []
            
            if isinstance(params_schema, dict):
                properties = params_schema.get('properties', {})
                required = params_schema.get('required', [])
                
                for param_name, param_info in properties.items():
                    param_type = param_info.get('type', 'string') if isinstance(param_info, dict) else str(param_info)
                    param_desc = param_info.get('description', '') if isinstance(param_info, dict) else ''
                    required_marker = " (REQUIRED)" if param_name in required else ""
                    
                    param_details.append(f'  "{param_name}": <{param_type}>{required_marker} - {param_desc}')
                    if param_name in required:
                        required_params.append(param_name)
            
            functions_text += f"- {func_name}: {func_desc}\n"
            if param_details:
                functions_text += "  Parameters:\n" + "\n".join(param_details) + "\n"
        
        # Create a focused prompt for function selection and parameter extraction
        prompt = f"""User request: "{user_prompt}"

{functions_text}

Analyze the user request and:
1. Select the most appropriate function
2. Extract parameter values from the user's request

CRITICAL RULES:
- Use the EXACT parameter names shown above for each function
- Extract actual values from the user request, don't make up placeholder values
- If a required parameter cannot be determined from the user request, use <UNKNOWN>
- Return ONLY valid JSON in this format:

{{"function": "function_name", "parameters": {{"exact_param_name": "extracted_value"}}}}

Example for get_shortest_driving_distance:
{{"function": "get_shortest_driving_distance", "parameters": {{"origin": "New York City", "destination": "Washington D.C.", "unit": "km"}}}}"""

        # Call LLM for function selection and parameter extraction
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
        
        # Parse and validate the JSON response
        try:
            llm_response = json.loads(content)
            validated = FunctionCall(**llm_response)
            
            # Return in the required format: {function_name: {parameters}}
            return {
                validated.function: validated.parameters
            }
            
        except (json.JSONDecodeError, ValueError) as e:
            # Try to extract function call with regex as fallback
            func_match = re.search(r'"function":\s*"([^"]+)"', content)
            params_match = re.search(r'"parameters":\s*(\{[^}]*\})', content)
            
            if func_match and params_match:
                func_name = func_match.group(1)
                try:
                    params = json.loads(params_match.group(1))
                    return {func_name: params}
                except json.JSONDecodeError:
                    pass
            
            return {"error": f"Failed to parse LLM response as JSON: {e}"}
            
    except Exception as e:
        return {"error": f"Function selection failed: {e}"}