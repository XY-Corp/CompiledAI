from typing import Any, Dict, List, Optional
import asyncio
import json
import re
from pydantic import BaseModel

class QuadraticEquationCall(BaseModel):
    """Expected structure for solve_quadratic_equation function call."""
    solve_quadratic_equation: Dict[str, int]

async def parse_equation_parameters(
    prompt_text: str,
    functions_list: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extract quadratic equation coefficients from natural language text and format as function call.
    
    Args:
        prompt_text: The natural language text containing the quadratic equation request with coefficient values
        functions_list: List of available function definitions that can be called
        
    Returns:
        Function call with function name as key and parameters object as value.
        Returns: {"solve_quadratic_equation": {"a": integer_value, "b": integer_value, "c": integer_value}}
    """
    try:
        # Handle JSON string input defensively
        if isinstance(functions_list, str):
            functions_list = json.loads(functions_list)
        
        # First try to extract coefficients using regex patterns
        # Look for patterns like "ax² + bx + c", "2x² + 6x + 5", etc.
        
        # Pattern 1: Standard form like "2x² + 6x + 5" or "ax² + bx + c"
        standard_pattern = r'(-?\d*)\s*x\s*\²?\s*\+?\s*(-?\d*)\s*x\s*\+?\s*(-?\d+)'
        match = re.search(standard_pattern, prompt_text.replace('²', '2').replace('^2', '2'))
        
        if match:
            a_str, b_str, c_str = match.groups()
            
            # Handle coefficient parsing
            a = int(a_str) if a_str and a_str not in ['', '+', '-'] else (1 if a_str != '-' else -1)
            b = int(b_str) if b_str and b_str not in ['', '+', '-'] else (1 if b_str != '-' else -1)
            c = int(c_str) if c_str else 0
            
            return {
                "solve_quadratic_equation": {
                    "a": a,
                    "b": b,
                    "c": c
                }
            }
        
        # Pattern 2: Look for explicit coefficient mentions like "a=2, b=6, c=5"
        coeff_pattern = r'a\s*=\s*(-?\d+).*?b\s*=\s*(-?\d+).*?c\s*=\s*(-?\d+)'
        match = re.search(coeff_pattern, prompt_text, re.IGNORECASE)
        
        if match:
            a, b, c = map(int, match.groups())
            return {
                "solve_quadratic_equation": {
                    "a": a,
                    "b": b,
                    "c": c
                }
            }
        
        # Pattern 3: Individual number extraction from context
        numbers = re.findall(r'-?\d+', prompt_text)
        if len(numbers) >= 3:
            # Take first three numbers as a, b, c
            a, b, c = map(int, numbers[:3])
            return {
                "solve_quadratic_equation": {
                    "a": a,
                    "b": b,
                    "c": c
                }
            }
        
        # If regex patterns fail, use LLM as fallback
        prompt = f"""Extract the quadratic equation coefficients from this text: "{prompt_text}"

A quadratic equation has the form ax² + bx + c = 0, where:
- a is the coefficient of x²
- b is the coefficient of x  
- c is the constant term

Return ONLY valid JSON in this exact format:
{{"a": integer_value, "b": integer_value, "c": integer_value}}

Examples:
- "2x² + 6x + 5" → {{"a": 2, "b": 6, "c": 5}}
- "x² - 4x + 3" → {{"a": 1, "b": -4, "c": 3}}
- "3x² + 2x - 1" → {{"a": 3, "b": 2, "c": -1}}"""

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
            coeffs = json.loads(content)
            
            # Validate we have the required coefficients
            if not all(key in coeffs for key in ['a', 'b', 'c']):
                return {"solve_quadratic_equation": {"a": 1, "b": 0, "c": 0}}
            
            # Ensure values are integers
            result = {
                "solve_quadratic_equation": {
                    "a": int(coeffs['a']),
                    "b": int(coeffs['b']),
                    "c": int(coeffs['c'])
                }
            }
            
            # Validate with Pydantic
            validated = QuadraticEquationCall(**result)
            return validated.model_dump()
            
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            # Final fallback - return default quadratic
            return {
                "solve_quadratic_equation": {
                    "a": 1,
                    "b": 0,
                    "c": 0
                }
            }
            
    except Exception as e:
        # Error fallback
        return {
            "solve_quadratic_equation": {
                "a": 1,
                "b": 0,
                "c": 0
            }
        }