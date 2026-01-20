from typing import Any, Dict, List, Optional
import asyncio
import json
import re
from pydantic import BaseModel

class FunctionSelection(BaseModel):
    """Expected structure for function selection."""
    function: str
    parameters: Dict[str, Any]

async def analyze_user_request(
    user_request: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Analyze the user request and available functions to determine which function to call with appropriate parameters.
    
    Args:
        user_request: The natural language request from the user that needs to be mapped to a function call
        available_functions: List of available functions with their names and parameter schemas that can be called
    
    Returns:
        Dict with selected function call in format: {"function": "get_weather", "parameters": {"location": "Paris", "unit": "celsius"}}
    """
    try:
        # Handle JSON string input defensively
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)
        
        if not isinstance(available_functions, list):
            return {"error": f"available_functions must be list, got {type(available_functions).__name__}"}
        
        if not user_request or not available_functions:
            return {"error": "Both user_request and available_functions are required"}
        
        # Format functions with EXACT parameter names clearly visible
        functions_text = "Available Functions:\n"
        for func in available_functions:
            # Check both 'parameters' and 'params' keys for compatibility
            params_schema = func.get('parameters', func.get('params', {}))
            
            # Show EXACT parameter names the LLM must use
            param_details = []
            for param_name, param_info in params_schema.items():
                # Handle both string format ("string") and dict format ({"type": "string", ...})
                if isinstance(param_info, str):
                    param_type = param_info
                else:
                    param_type = param_info.get('type', 'string')
                param_details.append(f'"{param_name}": <{param_type}>')
            
            functions_text += f"- {func['name']}: parameters must be: {{{', '.join(param_details)}}}\n"
        
        prompt = f"""User request: "{user_request}"
{functions_text}

Select the appropriate function and extract parameters from the user request.

CRITICAL: Use the EXACT parameter names shown above for each function.
DO NOT infer different parameter names.

For weather requests, common patterns:
- Location extraction: "weather in Paris" → location: "Paris"
- Unit extraction: "celsius/fahrenheit" → unit: "celsius" or "fahrenheit"
- Time extraction: "tomorrow", "next week" → extract relevant time values

Return ONLY valid JSON in this exact format:
{{"function": "function_name", "parameters": {{"exact_param_name": "value"}}}}

Examples:
- "What's the weather in London?" → {{"function": "get_weather", "parameters": {{"location": "London"}}}}
- "Temperature in Tokyo in celsius" → {{"function": "get_weather", "parameters": {{"location": "Tokyo", "unit": "celsius"}}}}"""

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
        
        # Parse and validate with Pydantic
        data = json.loads(content)
        validated = FunctionSelection(**data)
        return validated.model_dump()
        
    except json.JSONDecodeError as e:
        return {"error": f"Failed to parse LLM response as JSON: {e}"}
    except ValueError as e:
        return {"error": f"Invalid function selection format: {e}"}
    except Exception as e:
        return {"error": f"Failed to analyze user request: {e}"}