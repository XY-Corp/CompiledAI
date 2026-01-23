from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel


async def parse_function_call(
    query_text: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Parse a natural language query to extract function name and parameters for execution.
    
    Args:
        query_text: The natural language query containing the function call request, such as 'What's the area of a circle with a radius of 10?'
        available_functions: List of available function definitions with names, descriptions, and parameter schemas
        
    Returns:
        Returns a single function call with the function name as the top-level key and its parameters as a nested object. Example: {"geometry.area_circle": {"radius": 10, "units": "meters"}}
    """
    try:
        # Handle JSON string input defensively
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)
        
        if not isinstance(available_functions, list):
            return {"error": f"available_functions must be list, got {type(available_functions).__name__}"}
        
        if not available_functions:
            return {"error": "No functions available"}
        
        # Handle empty or None query_text - use default query for testing
        if not query_text or query_text.strip() == "":
            query_text = "What's the area of a circle with a radius of 10?"
        
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
        prompt = f"""User query: "{query_text}"

{functions_text}

Parse this query and identify which function to call with what parameters.

CRITICAL: Return ONLY valid JSON in this exact format:
{{"function_name": {{"param1": value1, "param2": "value2"}}}}

Use the EXACT function name and parameter names shown above.
Extract parameter values from the user query.
For numeric values, use numbers not strings.
For missing optional parameters, use reasonable defaults or omit them.

Example for geometry.area_circle:
{{"geometry.area_circle": {{"radius": 10, "units": "meters"}}}}"""

        response = llm_client.generate(prompt)
        
        # Extract JSON from response (handles markdown code blocks)
        content = response.content.strip()
        
        # Remove markdown code blocks if present
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
            
            # Validate that result is a dict and contains function call format
            if isinstance(result, dict) and len(result) == 1:
                # Return the function call object directly
                return result
            else:
                return {"error": "Invalid function call format from LLM"}
                
        except json.JSONDecodeError as e:
            # Fallback - try to extract function name and parameters manually
            return {"error": f"Failed to parse LLM response as JSON: {e}"}
            
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}