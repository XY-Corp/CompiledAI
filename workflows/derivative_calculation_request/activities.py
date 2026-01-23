from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel

class FunctionCallResponse(BaseModel):
    """Expected structure for derivative function call."""
    calculate_derivative: Dict[str, Any]

async def extract_function_call(
    query_text: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Parses natural language mathematical query to extract the polynomial function and optional x-value, then formats it as a proper function call request.

    Args:
        query_text: The natural language query containing the mathematical function to differentiate
        available_functions: List of available mathematical functions with their parameter schemas for context

    Returns:
        Dict containing function call request with calculate_derivative as key and parameters object
    """
    try:
        # Handle JSON string input defensively
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)

        if not isinstance(available_functions, list):
            return {"calculate_derivative": {"error": f"available_functions must be list, got {type(available_functions).__name__}"}}

        # Find the calculate_derivative function in available functions
        derivative_function = None
        for func in available_functions:
            if func.get('name') == 'calculate_derivative':
                derivative_function = func
                break

        if not derivative_function:
            return {"calculate_derivative": {"error": "calculate_derivative function not found in available functions"}}

        # Get parameter schema for calculate_derivative
        params_schema = derivative_function.get('parameters', {})
        if isinstance(params_schema, dict):
            properties = params_schema.get('properties', {})
        else:
            properties = {}

        # Extract mathematical function using patterns
        function_expr = None
        x_value = None

        # Common mathematical function patterns
        # Pattern 1: "derivative of 3x^2 + 2x - 1"
        derivative_match = re.search(r'derivative of\s+([^,.\n]+)', query_text, re.IGNORECASE)
        if derivative_match:
            function_expr = derivative_match.group(1).strip()

        # Pattern 2: "differentiate 3x^2 + 2x - 1"
        if not function_expr:
            diff_match = re.search(r'differentiate\s+([^,.\n]+)', query_text, re.IGNORECASE)
            if diff_match:
                function_expr = diff_match.group(1).strip()

        # Pattern 3: "find derivative: 3x^2 + 2x - 1"
        if not function_expr:
            find_match = re.search(r'find\s+derivative[:\s]+([^,.\n]+)', query_text, re.IGNORECASE)
            if find_match:
                function_expr = find_match.group(1).strip()

        # Pattern 4: Just a mathematical expression (fallback)
        if not function_expr:
            # Look for mathematical expressions with x
            expr_match = re.search(r'([0-9x\^\*\+\-\s]+(?:x[^,.\n]*)?)', query_text)
            if expr_match:
                potential_expr = expr_match.group(1).strip()
                # Only use if it contains 'x' (indicating it's a function of x)
                if 'x' in potential_expr:
                    function_expr = potential_expr

        # Extract x-value if mentioned
        x_match = re.search(r'(?:at\s+x\s*=\s*|when\s+x\s*=\s*|x\s*=\s*)([+-]?\d+(?:\.\d+)?)', query_text)
        if x_match:
            try:
                x_value = float(x_match.group(1))
            except ValueError:
                x_value = 0.0

        # If no function found, use LLM as fallback
        if not function_expr:
            prompt = f"""Extract the mathematical function from this query: "{query_text}"

Return ONLY the mathematical function in standard algebraic notation (like "3x^2 + 2x - 1").
Do not include any explanations or additional text."""

            response = llm_client.generate(prompt)
            function_expr = response.content.strip()

            # Clean up LLM response
            if function_expr:
                # Remove common prefixes/suffixes
                function_expr = re.sub(r'^(function[:\s]*|f\(x\)\s*=\s*)', '', function_expr, flags=re.IGNORECASE)
                function_expr = function_expr.strip(' "\'')

        # Normalize function expression
        if function_expr:
            # Convert ** to ^ for standard mathematical notation
            function_expr = function_expr.replace('**', '^')
            # Clean up extra spaces
            function_expr = re.sub(r'\s+', ' ', function_expr).strip()

        # Build parameters based on schema
        parameters = {}
        
        if 'function' in properties and function_expr:
            parameters['function'] = function_expr
        
        if 'x_value' in properties:
            if x_value is not None:
                parameters['x_value'] = x_value
            else:
                # Use default value if specified in schema or 0.0
                parameters['x_value'] = 0.0

        # If no parameters extracted, return error
        if not parameters:
            return {"calculate_derivative": {"error": "Could not extract mathematical function from query"}}

        result = {"calculate_derivative": parameters}
        
        # Validate with Pydantic
        try:
            validated = FunctionCallResponse(**result)
            return validated.model_dump()
        except Exception as e:
            # Return the result anyway if Pydantic validation fails
            return result

    except json.JSONDecodeError as e:
        return {"calculate_derivative": {"error": f"Invalid JSON in available_functions: {e}"}}
    except Exception as e:
        return {"calculate_derivative": {"error": f"Unexpected error: {e}"}}