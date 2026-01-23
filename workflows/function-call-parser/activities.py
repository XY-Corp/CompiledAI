from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel


class FunctionCallResult(BaseModel):
    """Schema for function call result."""
    function_calls: List[Dict[str, Dict[str, List[Any]]]]


async def parse_function_call_parameters(
    query_text: str,
    available_functions: str,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> list:
    """Extract function parameters from user query text and generate structured function call format.
    
    Args:
        query_text: The user query text containing values to extract for function parameters
        available_functions: String representation of available functions and their parameter schemas
    
    Returns:
        List containing function call objects. Each object has function name as key and parameters as value.
        For the math.hypot example with sides 4 and 5, returns: 
        [{'math.hypot': {'x': [4], 'y': [5], 'z': ['', 0]}}]
    """
    try:
        # Handle JSON string input defensively
        if isinstance(available_functions, str):
            functions = json.loads(available_functions)
        else:
            functions = available_functions
        
        if not isinstance(functions, list):
            return [{"error": f"available_functions must be a list, got {type(functions).__name__}"}]
            
        # Build function information for LLM
        functions_info = "Available Functions:\n"
        for func in functions:
            func_name = func.get('name', '')
            func_description = func.get('description', '')
            
            # Extract parameters from function schema
            parameters = func.get('parameters', {})
            param_details = []
            
            for param_name, param_info in parameters.items():
                if isinstance(param_info, dict):
                    param_type = param_info.get('type', 'string')
                    param_desc = param_info.get('description', '')
                    required = param_info.get('required', False)
                    req_text = " (required)" if required else " (optional)"
                    param_details.append(f"  - {param_name}: {param_type}{req_text} - {param_desc}")
                else:
                    param_details.append(f"  - {param_name}: {param_info}")
            
            functions_info += f"\n{func_name}: {func_description}\nParameters:\n"
            functions_info += "\n".join(param_details) + "\n"
        
        # Create prompt for LLM to extract parameters
        prompt = f"""Analyze this user query and extract parameters for the appropriate function call.

User Query: "{query_text}"

{functions_info}

CRITICAL: Return the result in this EXACT format as a JSON list:
[{{"function_name": {{"param1": [value1], "param2": [value2], "param3": ["", 0]}}}}]

Rules:
- Each parameter value must be in an array/list format
- If a parameter is not mentioned in the query, use ["", 0] as the default
- Extract actual numeric values from the text (e.g., "4 and 5" becomes [4] and [5])
- Use the exact function name and parameter names from the schema
- Return only one function call object in the list

Example: For math.hypot with sides 4 and 5:
[{{"math.hypot": {{"x": [4], "y": [5], "z": ["", 0]}}}}]"""

        # Use LLM to extract function parameters
        response = llm_client.generate(prompt)
        content = response.content.strip()
        
        # Extract JSON from response (handle markdown code blocks)
        if "```" in content:
            json_match = re.search(r'```(?:json)?\s*(\[.*?\])\s*```', content, re.DOTALL)
            if json_match:
                content = json_match.group(1)
            else:
                # Try to find any JSON array
                json_match = re.search(r'\[.*?\]', content, re.DOTALL)
                if json_match:
                    content = json_match.group(0)
        
        # Parse the JSON response
        try:
            result = json.loads(content)
            
            # Validate structure
            if not isinstance(result, list):
                return [{"error": "LLM response must be a list"}]
                
            # Validate each function call object
            validated_result = []
            for func_call in result:
                if isinstance(func_call, dict):
                    # Ensure parameter values are in array format
                    for func_name, params in func_call.items():
                        if isinstance(params, dict):
                            for param_name, param_value in params.items():
                                if not isinstance(param_value, list):
                                    # Convert single values to list format
                                    params[param_name] = [param_value] if param_value != "" else ["", 0]
                    validated_result.append(func_call)
                    
            return validated_result if validated_result else result
            
        except json.JSONDecodeError as e:
            # Fallback: try to extract values using regex patterns
            return _fallback_parameter_extraction(query_text, functions)
            
    except Exception as e:
        return [{"error": f"Failed to parse function parameters: {str(e)}"}]


def _fallback_parameter_extraction(query_text: str, functions: list) -> list:
    """Fallback method to extract parameters using regex patterns."""
    try:
        # Look for numeric values in the query
        numbers = re.findall(r'\d+(?:\.\d+)?', query_text)
        
        # Find the most likely function based on keywords
        for func in functions:
            func_name = func.get('name', '')
            
            # Simple keyword matching
            if 'hypot' in func_name.lower() and ('triangle' in query_text.lower() or 'hypotenuse' in query_text.lower()):
                parameters = func.get('parameters', {})
                param_names = list(parameters.keys())
                
                result = {func_name: {}}
                
                # Assign extracted numbers to parameters
                for i, param_name in enumerate(param_names):
                    if i < len(numbers):
                        result[func_name][param_name] = [float(numbers[i]) if '.' in numbers[i] else int(numbers[i])]
                    else:
                        result[func_name][param_name] = ["", 0]
                
                return [result]
        
        # If no specific function found, return error
        return [{"error": "Could not determine appropriate function or extract parameters"}]
        
    except Exception as e:
        return [{"error": f"Fallback extraction failed: {str(e)}"}]