from typing import Any, Dict, List, Optional
import asyncio
import json
import re
from pydantic import BaseModel

class FunctionCall(BaseModel):
    """Expected structure for quadratic function call."""
    a: int
    b: int
    c: int
    root_type: str = "all"

async def extract_quadratic_parameters(
    input_text: str,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extract quadratic equation coefficients from natural language text and format as function call.

    Args:
        input_text: Natural language text describing a quadratic equation with coefficients to extract

    Returns:
        Dict with solve_quadratic function call structure
    """
    # First try regex patterns for structured quadratic equations
    
    # Pattern 1: Standard form like "3x^2 - 11x - 4" or "3x² - 11x - 4"
    quadratic_pattern = r'([+-]?\d*\.?\d*)\s*x\s*[\^²2]\s*([+-]\s*\d*\.?\d*)\s*x\s*([+-]\s*\d+\.?\d*)'
    match = re.search(quadratic_pattern, input_text.replace(' ', ''))
    
    if match:
        a_str = match.group(1).replace(' ', '')
        b_str = match.group(2).replace(' ', '')
        c_str = match.group(3).replace(' ', '')
        
        # Handle coefficient parsing
        a = 1 if a_str in ['', '+'] else -1 if a_str == '-' else int(float(a_str))
        b = 1 if b_str in ['+'] else -1 if b_str == '-' else int(float(b_str)) if b_str else 0
        c = int(float(c_str)) if c_str else 0
        
        # Check for root_type hints in the text
        root_type = "real" if "real" in input_text.lower() and "only" in input_text.lower() else "all"
        
        return {
            "solve_quadratic": {
                "a": a,
                "b": b,
                "c": c,
                "root_type": root_type
            }
        }
    
    # Pattern 2: Look for explicit coefficients like "a=3, b=-11, c=-4"
    coeff_pattern = r'a\s*=\s*([+-]?\d+).*?b\s*=\s*([+-]?\d+).*?c\s*=\s*([+-]?\d+)'
    match = re.search(coeff_pattern, input_text, re.IGNORECASE)
    
    if match:
        a = int(match.group(1))
        b = int(match.group(2))
        c = int(match.group(3))
        
        root_type = "real" if "real" in input_text.lower() and "only" in input_text.lower() else "all"
        
        return {
            "solve_quadratic": {
                "a": a,
                "b": b,
                "c": c,
                "root_type": root_type
            }
        }
    
    # Pattern 3: Look for numbers in sequence that could be coefficients
    numbers = re.findall(r'([+-]?\d+)', input_text)
    if len(numbers) >= 3:
        try:
            a = int(numbers[0])
            b = int(numbers[1]) 
            c = int(numbers[2])
            
            root_type = "real" if "real" in input_text.lower() and "only" in input_text.lower() else "all"
            
            return {
                "solve_quadratic": {
                    "a": a,
                    "b": b,
                    "c": c,
                    "root_type": root_type
                }
            }
        except (ValueError, IndexError):
            pass
    
    # If regex patterns fail, use LLM as fallback
    prompt = f"""Extract the quadratic equation coefficients from this text: {input_text}

A quadratic equation has the form ax² + bx + c = 0, where:
- a is the coefficient of x² (cannot be 0)
- b is the coefficient of x
- c is the constant term

Also determine if only real roots are wanted or all roots (including complex).

Return ONLY valid JSON in this exact format:
{{"a": 3, "b": -11, "c": -4, "root_type": "all"}}

Where root_type is "real" if only real roots are requested, otherwise "all"."""

    try:
        response = llm_client.generate(prompt)
        content = response.content.strip()
        
        # Remove markdown code blocks if present
        if "```" in content:
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
            if json_match:
                content = json_match.group(1)
            else:
                json_match = re.search(r'\{.*?\}', content, re.DOTALL)
                if json_match:
                    content = json_match.group(0)
        
        # Parse and validate with Pydantic
        data = json.loads(content)
        validated = FunctionCall(**data)
        
        return {
            "solve_quadratic": validated.model_dump()
        }
        
    except (json.JSONDecodeError, ValueError) as e:
        # Default fallback if everything fails
        return {
            "solve_quadratic": {
                "a": 1,
                "b": 0,
                "c": 0,
                "root_type": "all"
            }
        }