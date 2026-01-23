from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel


class IntegrationCall(BaseModel):
    """Validates the structure of an integration function call."""
    integrate: Dict[str, Any]


async def parse_integration_request(
    prompt: str,
    functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extract integration function parameters from natural language prompt.
    
    Args:
        prompt: The natural language request containing function, bounds, and method information for numerical integration
        functions: List of available function definitions for context about expected parameters and format
        
    Returns:
        A single function call with the function name as the top-level key and its parameters as a nested object.
        The integrate key contains function (string representation like 'x^3'), start_x (integer starting bound), 
        end_x (integer ending bound), and method (string specifying 'trapezoid' or 'simpson' integration method).
    """
    try:
        # Handle JSON string input defensively
        if isinstance(functions, str):
            functions = json.loads(functions)
        
        if not isinstance(functions, list):
            return {"error": f"functions must be list, got {type(functions).__name__}"}
        
        if not functions:
            return {"error": "No functions available"}
        
        # Build function descriptions for the LLM with EXACT parameter names
        functions_text = "Available Functions:\n"
        for func in functions:
            func_name = func.get('name', 'unknown')
            func_desc = func.get('description', 'No description')
            
            # Handle parameters schema - check both 'parameters' and 'params' keys
            params_schema = func.get('parameters', func.get('params', {}))
            
            functions_text += f"- {func_name}: {func_desc}\n"
            
            # Extract parameter details with exact names and types
            if isinstance(params_schema, dict):
                properties = params_schema.get('properties', params_schema)
                
                if properties:
                    functions_text += f"  Parameters (use EXACT names):\n"
                    for param_name, param_info in properties.items():
                        if isinstance(param_info, dict):
                            param_type = param_info.get('type', 'string')
                            param_desc = param_info.get('description', '')
                        else:
                            param_type = str(param_info)
                            param_desc = ''
                        functions_text += f"    - {param_name}: {param_type} - {param_desc}\n"
            functions_text += "\n"
        
        # Create clean prompt asking for specific integration format
        clean_prompt = f"""User request: "{prompt}"

{functions_text}

Extract the integration parameters from the user request.

CRITICAL: Use EXACT parameter names shown above.
- function: Mathematical expression as a string (e.g., "x^3", "x**2 + 1", "sin(x)")
- start_x: Starting bound as integer
- end_x: Ending bound as integer  
- method: Integration method as string ("trapezoid" or "simpson")

Return ONLY valid JSON in this exact format:
{{"integrate": {{"function": "x^3", "start_x": -2, "end_x": 3, "method": "simpson"}}}}"""
        
        response = llm_client.generate(clean_prompt)
        
        # Extract JSON from response (handles markdown code blocks)
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
        
        # Parse and validate with Pydantic
        try:
            data = json.loads(content)
            validated = IntegrationCall(**data)
            return validated.model_dump()
        except (json.JSONDecodeError, ValueError) as e:
            # Try to extract using regex patterns as fallback
            return _extract_integration_fallback(prompt)
            
    except json.JSONDecodeError as e:
        return {"error": f"Invalid JSON in functions parameter: {e}"}
    except Exception as e:
        return {"error": f"Failed to parse integration request: {e}"}


def _extract_integration_fallback(prompt: str) -> dict[str, Any]:
    """Fallback extraction using regex patterns when LLM fails."""
    try:
        # Initialize default values
        function = ""
        start_x = 0
        end_x = 1
        method = "simpson"
        
        # Extract function - look for common mathematical expressions
        func_patterns = [
            r'function[:\s]+([x\^*+\-\d\s()sincostan]+)',
            r'integrate[:\s]+([x\^*+\-\d\s()sincostan]+)',
            r'of[:\s]+([x\^*+\-\d\s()sincostan]+)',
            r'([x\^*+\-\d]+(?:\s*[\+\-]\s*[x\^*+\-\d]+)*)'
        ]
        
        for pattern in func_patterns:
            match = re.search(pattern, prompt, re.IGNORECASE)
            if match:
                function = match.group(1).strip()
                # Normalize function format (x^3 or x**3)
                function = re.sub(r'\^', '**', function)
                break
        
        # Extract bounds
        bound_matches = re.findall(r'-?\d+', prompt)
        if len(bound_matches) >= 2:
            start_x = int(bound_matches[0])
            end_x = int(bound_matches[1])
        
        # Extract method
        if 'trapezoid' in prompt.lower():
            method = "trapezoid"
        elif 'simpson' in prompt.lower():
            method = "simpson"
        
        return {
            "integrate": {
                "function": function or "x",
                "start_x": start_x,
                "end_x": end_x,
                "method": method
            }
        }
        
    except Exception:
        return {
            "integrate": {
                "function": "x",
                "start_x": 0,
                "end_x": 1,
                "method": "simpson"
            }
        }