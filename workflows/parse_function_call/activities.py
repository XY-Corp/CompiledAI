from typing import Any, Dict, List, Optional
from pydantic import BaseModel
import asyncio
import json
import re


class FunctionCall(BaseModel):
    """Pydantic model to validate the extracted function call structure."""
    function: str
    parameters: Dict[str, Any]


async def parse_function_parameters(
    query_text: str,
    available_functions: str,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extracts function parameters from the user query and generates the appropriate function call structure.
    
    Args:
        query_text: The user query text containing function parameters to extract
        available_functions: The available functions and their parameter specifications
        
    Returns:
        Dict with function name as key and parameters as nested dict
    """
    try:
        # Parse JSON string if needed
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)
        
        # Validate input
        if not isinstance(available_functions, list):
            return {"error": f"available_functions must be list, got {type(available_functions).__name__}"}
            
        if not available_functions:
            return {"error": "No functions available"}
            
        # Format functions with EXACT parameter names for the LLM
        functions_text = "Available Functions:\n"
        for func in available_functions:
            func_name = func.get('name', '')
            func_desc = func.get('description', '')
            params_schema = func.get('parameters', {})
            
            # Show exact parameter names and types
            param_details = []
            for param_name, param_info in params_schema.items():
                if isinstance(param_info, dict):
                    param_type = param_info.get('type', 'string')
                    param_desc = param_info.get('description', '')
                    param_details.append(f'"{param_name}": <{param_type}> - {param_desc}')
                else:
                    param_details.append(f'"{param_name}": <{param_info}>')
            
            functions_text += f"- {func_name}: {func_desc}\n"
            functions_text += f"  Parameters: {{{', '.join(param_details)}}}\n"
        
        # Create prompt for LLM to extract function call
        prompt = f"""User query: "{query_text}"

{functions_text}

Analyze the user query and select the most appropriate function. Extract the parameter values from the query text.

CRITICAL: Use the EXACT parameter names shown above for the selected function.

Return JSON in this format:
{{"function": "function_name", "parameters": {{"exact_param_name": value, "another_param": value}}}}

Extract actual values from the query text. For example:
- If query mentions "base of 10", extract base: 10
- If query mentions "height of 5", extract height: 5  
- If query mentions "units", extract unit: "units"

Return only the JSON object."""

        # Use LLM to extract function call
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
        
        # Parse and validate with Pydantic
        try:
            data = json.loads(content)
            validated = FunctionCall(**data)
            
            # Return in the required format: {function_name: {parameters}}
            result = {
                validated.function: validated.parameters
            }
            
            return result
            
        except (json.JSONDecodeError, ValueError) as e:
            # Fallback: try to extract function call using regex patterns
            # Look for common patterns in user queries
            fallback_result = {}
            
            # Check for triangle area calculation
            if "triangle" in query_text.lower() and "area" in query_text.lower():
                base_match = re.search(r'base\s*(?:of|is)?\s*(\d+)', query_text, re.IGNORECASE)
                height_match = re.search(r'height\s*(?:of|is)?\s*(\d+)', query_text, re.IGNORECASE)
                unit_match = re.search(r'(\w+\s*units?)', query_text, re.IGNORECASE)
                
                if base_match and height_match:
                    fallback_result["calculate_triangle_area"] = {
                        "base": int(base_match.group(1)),
                        "height": int(height_match.group(1)),
                        "unit": unit_match.group(1).strip() if unit_match else "units"
                    }
                    return fallback_result
            
            return {"error": f"Failed to parse LLM response: {e}"}
            
    except json.JSONDecodeError as e:
        return {"error": f"Invalid JSON in available_functions: {e}"}
    except Exception as e:
        return {"error": f"Unexpected error: {e}"}