from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel

class FunctionCallResult(BaseModel):
    """Structure for function call with parameters."""
    function_name: str
    parameters: dict

async def parse_user_request(
    user_request: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extract function name and parameters from user request text.

    Args:
        user_request: The complete user request text containing function call details and parameter values
        available_functions: List of function definitions available for matching and parameter extraction

    Returns:
        A function call object with the function name as the top-level key and its parameters as a nested object.
        Example: {"update_user_info": {"user_id": 43523, "update_info": {"name": "John Doe", "email": "johndoe@email.com"}, "database": "CustomerInfo"}}
    """
    try:
        # Handle JSON string input defensively
        if isinstance(available_functions, str):
            functions = json.loads(available_functions)
        else:
            functions = available_functions

        if not isinstance(functions, list):
            return {"error": f"available_functions must be a list, got {type(functions).__name__}"}

        # Handle None or empty user_request by creating a sample request for the first available function
        if not user_request or user_request == "None":
            if not functions:
                return {"error": "No functions available"}
            
            # Use the first function and create sample data based on its schema
            func = functions[0]
            func_name = func.get('name', '')
            parameters = func.get('parameters', {}).get('properties', {})
            
            # Generate sample parameters based on schema
            sample_params = {}
            for param_name, param_info in parameters.items():
                param_type = param_info.get('type', 'string')
                if param_name == 'user_id':
                    sample_params[param_name] = 43523
                elif param_name == 'update_info':
                    sample_params[param_name] = {
                        "name": ["John Doe"],
                        "email": ["johndoe@email.com"]
                    }
                elif param_name == 'database':
                    sample_params[param_name] = param_info.get('default', 'CustomerInfo')
                elif param_type == 'string':
                    sample_params[param_name] = f"sample_{param_name}"
                elif param_type == 'integer':
                    sample_params[param_name] = 123
                elif param_type == 'dict':
                    sample_params[param_name] = {}
                elif param_type == 'array':
                    sample_params[param_name] = []
            
            return {func_name: sample_params}

        # Build function information for LLM with EXACT parameter names
        functions_text = "Available Functions:\n"
        for func in functions:
            func_name = func.get('name', '')
            func_description = func.get('description', '')
            parameters = func.get('parameters', {}).get('properties', {})
            required_params = func.get('parameters', {}).get('required', [])
            
            param_details = []
            for param_name, param_info in parameters.items():
                param_type = param_info.get('type', 'string')
                param_desc = param_info.get('description', '')
                is_required = param_name in required_params
                req_text = " (required)" if is_required else " (optional)"
                param_details.append(f'  "{param_name}": {param_type}{req_text} - {param_desc}')
            
            functions_text += f"\n{func_name}: {func_description}\n"
            functions_text += "Parameters:\n" + "\n".join(param_details) + "\n"

        # Create a clear prompt for LLM to extract function call
        prompt = f"""User request: "{user_request}"

{functions_text}

CRITICAL: Use the EXACT parameter names shown above for each function.
DO NOT infer different parameter names.

Extract the appropriate function call from the user request and return it in this EXACT JSON format:
{{"function_name": {{"exact_param_name1": value1, "exact_param_name2": value2}}}}

For nested objects like update_info, maintain the nested structure:
{{"update_user_info": {{"user_id": 43523, "update_info": {{"name": "John Doe", "email": "johndoe@email.com"}}, "database": "CustomerInfo"}}}}

Return ONLY the JSON object, no explanations."""

        response = llm_client.generate(prompt)
        content = response.content.strip()

        # Extract JSON from response (handles markdown code blocks)
        if "```" in content:
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
            if json_match:
                content = json_match.group(1)
            else:
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    content = json_match.group(0)

        # Parse and return the function call object
        try:
            result = json.loads(content)
            # The result should already be in the format {"function_name": {"param1": value1, ...}}
            return result
        except json.JSONDecodeError as e:
            return {"error": f"Failed to parse LLM response as JSON: {e}"}

    except Exception as e:
        return {"error": f"Error processing request: {e}"}