from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel


class FunctionCall(BaseModel):
    """Represents a function call with its parameters."""
    function: str
    parameters: Dict[str, Any]


async def analyze_user_query(
    user_question: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Parse user question to identify the appropriate function and extract parameters.
    
    Args:
        user_question: The natural language question from the user that needs to be analyzed
        available_functions: List of available function definitions with their names, descriptions, and parameter schemas
        
    Returns:
        Dict where the function name is the top-level key and parameters are nested
    """
    try:
        # Handle JSON string input defensively
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)
            
        if not isinstance(available_functions, list) or not available_functions:
            return {"error": "available_functions must be a non-empty list"}
            
        # Format functions with EXACT parameter names clearly visible
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
                    is_required = param_name in required_params
                    req_text = " (required)" if is_required else " (optional)"
                    
                    functions_text += f"    - {param_name}: {param_type}{req_text} - {param_desc}\n"
        
        prompt = f"""Analyze this user question and select the most appropriate function with parameters.

User Question: "{user_question}"

{functions_text}

CRITICAL INSTRUCTIONS:
1. Select the single most appropriate function from the list above
2. Use the EXACT parameter names shown for each function
3. Extract parameter values from the user question or make reasonable inferences
4. For boolean parameters, determine true/false based on the user's intent
5. Return ONLY valid JSON in this exact format:

{{"function_name": {{"param1": "value1", "param2": "value2"}}}}

Example if selecting cell_biology.function_lookup:
{{"cell_biology.function_lookup": {{"molecule": "ATP synthase", "organelle": "mitochondria", "specific_function": true}}}}

Return only the JSON object, no explanation or markdown:"""

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

        # Parse and validate JSON
        try:
            result = json.loads(content)
            
            # Validate that it's a dict with exactly one function key
            if not isinstance(result, dict):
                return {"error": "Response must be a JSON object"}
                
            if len(result) != 1:
                return {"error": "Response must contain exactly one function"}
                
            # Verify the function name exists in available functions
            function_name = list(result.keys())[0]
            function_names = [f.get('name') for f in available_functions]
            
            if function_name not in function_names:
                return {"error": f"Unknown function: {function_name}"}
                
            return result
            
        except json.JSONDecodeError as e:
            # Try to extract JSON from the response more aggressively
            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', content)
            if json_match:
                try:
                    result = json.loads(json_match.group(0))
                    return result
                except json.JSONDecodeError:
                    pass
                    
            return {"error": f"Failed to parse LLM response as JSON: {e}"}
            
    except Exception as e:
        return {"error": f"Analysis failed: {e}"}