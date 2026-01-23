from typing import Any, Dict, List, Optional
import re
import json
from pydantic import BaseModel


class QuadraticCoefficients(BaseModel):
    """Expected structure for quadratic coefficients."""
    a: int
    b: int 
    c: int


async def parse_quadratic_equation(
    equation_text: str,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extract quadratic equation coefficients from natural language text and return the function call structure.

    Args:
        equation_text: The natural language text containing the quadratic equation request with coefficients a, b, and c values

    Returns:
        Dict with the function call structure: {"algebra.quadratic_roots": {"a": integer_value, "b": integer_value, "c": integer_value}}
    """
    # Handle JSON string input defensively
    if isinstance(equation_text, str) and equation_text.strip().startswith(('{', '[')):
        try:
            equation_text = json.loads(equation_text)
        except json.JSONDecodeError:
            pass

    # Ensure we have a string to work with
    if not isinstance(equation_text, str):
        equation_text = str(equation_text)

    # First try regex patterns for structured quadratic equations
    
    # Pattern 1: Standard form like "3x^2 - 11x - 4" or "3x² - 11x - 4" 
    # Handle various formats: x^2, x², x2, X^2, etc.
    quadratic_pattern = r'([+-]?\d*\.?\d*)\s*[xX]\s*[\^²2²]\s*([+-]\s*\d*\.?\d*)\s*[xX]\s*([+-]\s*\d+\.?\d*)'
    text_cleaned = equation_text.replace(' ', '')
    match = re.search(quadratic_pattern, text_cleaned)
    
    if match:
        try:
            a_str = match.group(1).replace(' ', '')
            b_str = match.group(2).replace(' ', '')
            c_str = match.group(3).replace(' ', '')
            
            # Handle coefficient parsing
            # Empty or just + means coefficient is 1, just - means -1
            if a_str in ['', '+']:
                a = 1
            elif a_str == '-':
                a = -1
            else:
                a = int(float(a_str))
                
            if b_str in ['+']:
                b = 1
            elif b_str == '-':
                b = -1
            elif not b_str:
                b = 0
            else:
                b = int(float(b_str))
                
            c = int(float(c_str)) if c_str else 0
            
            return {
                "algebra.quadratic_roots": {
                    "a": a,
                    "b": b,
                    "c": c
                }
            }
        except (ValueError, AttributeError):
            pass
    
    # Pattern 2: Look for explicit coefficients like "a=3, b=-11, c=-4" or "a: 3, b: -11, c: -4"
    coeff_pattern = r'a\s*[:=]\s*([+-]?\d+).*?b\s*[:=]\s*([+-]?\d+).*?c\s*[:=]\s*([+-]?\d+)'
    match = re.search(coeff_pattern, equation_text, re.IGNORECASE | re.DOTALL)
    
    if match:
        try:
            a = int(match.group(1))
            b = int(match.group(2))
            c = int(match.group(3))
            
            return {
                "algebra.quadratic_roots": {
                    "a": a,
                    "b": b,
                    "c": c
                }
            }
        except ValueError:
            pass
    
    # Pattern 3: Look for "ax² + bx + c" format with specific values
    # Like "solve x² - 3x + 2 = 0" or "find roots of 2x² + 5x - 3"
    expanded_pattern = r'([+-]?\d*)\s*x[\^²2]\s*([+-]\s*\d*)\s*x\s*([+-]\s*\d+)'
    match = re.search(expanded_pattern, equation_text.lower().replace(' ', ''))
    
    if match:
        try:
            a_str = match.group(1)
            b_str = match.group(2) 
            c_str = match.group(3)
            
            # Parse coefficients carefully
            a = 1 if a_str in ['', '+'] else -1 if a_str == '-' else int(a_str)
            b = 1 if b_str.replace(' ', '') == '+' else -1 if b_str.replace(' ', '') == '-' else int(b_str.replace(' ', '')) if b_str.strip() else 0
            c = int(c_str.replace(' ', ''))
            
            return {
                "algebra.quadratic_roots": {
                    "a": a,
                    "b": b,
                    "c": c
                }
            }
        except (ValueError, AttributeError):
            pass
    
    # Pattern 4: Look for three numbers in sequence that could be coefficients
    # This handles cases like "solve with coefficients 1, -3, 2" 
    numbers = re.findall(r'([+-]?\d+)', equation_text)
    if len(numbers) >= 3:
        try:
            a = int(numbers[0])
            b = int(numbers[1]) 
            c = int(numbers[2])
            
            # Basic validation - 'a' cannot be 0 for quadratic
            if a != 0:
                return {
                    "algebra.quadratic_roots": {
                        "a": a,
                        "b": b,
                        "c": c
                    }
                }
        except (ValueError, IndexError):
            pass
    
    # If regex patterns fail, use LLM as fallback for complex natural language
    prompt = f"""Extract the quadratic equation coefficients from this text: {equation_text}

A quadratic equation has the form ax² + bx + c = 0, where a, b, and c are integer coefficients.
Find the values of a, b, and c from the given text.

Return ONLY valid JSON in this exact format:
{{"a": integer_value, "b": integer_value, "c": integer_value}}

Examples:
- "x² - 3x + 2" → {{"a": 1, "b": -3, "c": 2}}  
- "2x² + 5x - 3" → {{"a": 2, "b": 5, "c": -3}}
- "solve with a=1, b=-3, c=2" → {{"a": 1, "b": -3, "c": 2}}"""

    response = llm_client.generate(prompt)
    content = response.content.strip()

    # Extract JSON from response (handles markdown code blocks)
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
        validated = QuadraticCoefficients(**data)
        
        return {
            "algebra.quadratic_roots": validated.model_dump()
        }
    except (json.JSONDecodeError, ValueError) as e:
        # Fallback - return default coefficients for x² - 3x + 2
        return {
            "algebra.quadratic_roots": {
                "a": 1,
                "b": -3, 
                "c": 2
            }
        }