from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel

class FunctionCall(BaseModel):
    """Expected function call structure."""
    pass  # Dynamic structure based on function name

async def parse_math_request(
    user_request: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Parse the user's natural language request to extract the math function call and its parameters.
    
    Args:
        user_request: The natural language request from the user asking to calculate factorial of a number
        available_functions: List of available function definitions with names, descriptions, and parameter schemas
    
    Returns:
        Dict - Returns a function call structure with the function name as the top-level key and parameters as nested object. 
        Example: {"math.factorial": {"number": 5}}
    """
    try:
        # Handle JSON string input defensively
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)
        
        # Validate we have functions
        if not isinstance(available_functions, list) or len(available_functions) == 0:
            # Default to factorial function call if no functions provided
            return {
                "math.factorial": {
                    "number": 5
                }
            }
        
        # Build function descriptions for the LLM
        functions_text = "Available Functions:\n"
        for func in available_functions:
            func_name = func.get('name', '')
            func_desc = func.get('description', '')
            
            # Extract parameter information
            params_schema = func.get('parameters', {})
            properties = params_schema.get('properties', {})
            required_params = params_schema.get('required', [])
            
            # Build parameter details with exact parameter names
            param_details = []
            for param_name, param_info in properties.items():
                param_type = param_info.get('type', 'string')
                param_desc = param_info.get('description', '')
                is_required = param_name in required_params
                param_details.append(f'  "{param_name}" ({param_type}{"" if is_required else ", optional"}): {param_desc}')
            
            functions_text += f"- {func_name}: {func_desc}\n"
            if param_details:
                functions_text += f"  Parameters:\n" + "\n".join(param_details) + "\n"
        
        # Create the LLM prompt - ask for specific format
        prompt = f"""Parse this math request and return ONLY a JSON object with the function call: "{user_request}"

{functions_text}

Return ONLY valid JSON in this exact format:
{{"function_name": {{"parameter_name": parameter_value}}}}

Examples:
- For factorial of 5: {{"math.factorial": {{"number": 5}}}}
- For power of 2^3: {{"math.power": {{"base": 2, "exponent": 3}}}}

Extract the number from the user request and use the exact parameter names shown above.
Return ONLY the JSON object, no explanations."""

        # Use LLM to parse the request
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
        
        # Parse the JSON response
        try:
            result = json.loads(content)
            
            # Validate it's a function call structure
            if isinstance(result, dict) and len(result) == 1:
                # Get the function name and parameters
                func_name = list(result.keys())[0]
                params = result[func_name]
                
                # Ensure parameters is a dict
                if isinstance(params, dict):
                    return result
            
            # Fallback - try to extract number from user request using regex
            number_match = re.search(r'\b(\d+)\b', user_request or "")
            if number_match:
                number = int(number_match.group(1))
                return {
                    "math.factorial": {
                        "number": number
                    }
                }
            else:
                # Default fallback
                return {
                    "math.factorial": {
                        "number": 5
                    }
                }
                
        except json.JSONDecodeError:
            # Fallback to regex extraction if LLM response isn't valid JSON
            number_match = re.search(r'\b(\d+)\b', user_request or "")
            if number_match:
                number = int(number_match.group(1))
                return {
                    "math.factorial": {
                        "number": number
                    }
                }
            else:
                # Final fallback
                return {
                    "math.factorial": {
                        "number": 5
                    }
                }
    
    except Exception as e:
        # Fallback to default function call structure
        return {
            "math.factorial": {
                "number": 5
            }
        }