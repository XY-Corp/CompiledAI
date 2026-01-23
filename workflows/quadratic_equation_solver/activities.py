from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel

async def extract_quadratic_coefficients(
    user_prompt: str,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Parse the user prompt to extract coefficients a, b, and c for a quadratic equation and format them as a function call structure."""
    
    try:
        # Handle defensive input parsing
        if isinstance(user_prompt, dict) or isinstance(user_prompt, list):
            user_prompt = json.dumps(user_prompt) if not isinstance(user_prompt, str) else user_prompt
        
        if not user_prompt or not isinstance(user_prompt, str):
            # Return default coefficients if no valid prompt
            return {
                "solve_quadratic": {
                    "a": 1,
                    "b": 0,
                    "c": 0
                }
            }
        
        # Clean the prompt for better parsing
        cleaned_prompt = user_prompt.lower().replace('²', '^2').replace(' ', '')
        
        a, b, c = None, None, None
        
        # Pattern 1: Standard quadratic form like "2x^2 + 5x + 3" or "2x² + 5x + 3"
        # Handle various formats: ax^2+bx+c, ax²+bx+c, etc.
        pattern1 = r'(-?\d+)?x\^?2?\s*([+-]\s*\d+)?x\s*([+-]\s*\d+)?'
        match1 = re.search(pattern1, cleaned_prompt)
        
        if match1:
            # Extract coefficient a (defaults to 1 if not specified)
            a_str = match1.group(1)
            a = int(a_str) if a_str else 1
            
            # Extract coefficient b
            b_str = match1.group(2)
            if b_str:
                b_str = b_str.replace(' ', '').replace('+', '')
                b = int(b_str) if b_str else 0
            else:
                b = 0
            
            # Extract coefficient c
            c_str = match1.group(3)
            if c_str:
                c_str = c_str.replace(' ', '').replace('+', '')
                c = int(c_str) if c_str else 0
            else:
                c = 0
        
        # Pattern 2: Explicit coefficient assignment like "a=2, b=5, c=3"
        if a is None or b is None or c is None:
            a_match = re.search(r'a\s*=\s*(-?\d+)', user_prompt)
            b_match = re.search(r'b\s*=\s*(-?\d+)', user_prompt)
            c_match = re.search(r'c\s*=\s*(-?\d+)', user_prompt)
            
            if a_match and b_match and c_match:
                a = int(a_match.group(1))
                b = int(b_match.group(1))
                c = int(c_match.group(1))
        
        # Pattern 3: Look for individual numbers that could be coefficients
        if a is None or b is None or c is None:
            numbers = re.findall(r'-?\d+', user_prompt)
            if len(numbers) >= 3:
                # Use first three numbers found as coefficients
                a = int(numbers[0]) if a is None else a
                b = int(numbers[1]) if b is None else b
                c = int(numbers[2]) if c is None else c
        
        # Pattern 4: Special cases like "solve x^2 - 4 = 0" (missing middle term)
        if a is None or b is None or c is None:
            # Look for x^2 term
            x2_pattern = r'(-?\d+)?x\^?2'
            x2_match = re.search(x2_pattern, cleaned_prompt)
            if x2_match:
                a = int(x2_match.group(1)) if x2_match.group(1) else 1
            
            # Look for x term (not x^2)
            x_pattern = r'(?<!x)([+-]\s*\d+)x(?!\^)'
            x_match = re.search(x_pattern, cleaned_prompt)
            if x_match:
                b_str = x_match.group(1).replace(' ', '').replace('+', '')
                b = int(b_str)
            
            # Look for constant term
            const_pattern = r'([+-]\s*\d+)(?!x)'
            const_matches = re.findall(const_pattern, cleaned_prompt)
            if const_matches:
                # Take the last constant (likely the c term)
                c_str = const_matches[-1].replace(' ', '').replace('+', '')
                c = int(c_str)
        
        # Fallback to LLM if regex patterns fail
        if a is None or b is None or c is None:
            class QuadraticCoeffs(BaseModel):
                a: int
                b: int
                c: int
            
            prompt = f"""Extract the coefficients a, b, and c from this quadratic equation text:

"{user_prompt}"

A quadratic equation has the form ax² + bx + c = 0 where a, b, and c are the coefficients.

Return ONLY valid JSON in this exact format:
{{"a": integer_value, "b": integer_value, "c": integer_value}}

Examples:
- "2x² + 5x + 3" → {{"a": 2, "b": 5, "c": 3}}
- "x² - 4x + 4" → {{"a": 1, "b": -4, "c": 4}}
- "3x² - 2x" → {{"a": 3, "b": -2, "c": 0}}"""
            
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
            
            try:
                llm_data = json.loads(content)
                validated = QuadraticCoeffs(**llm_data)
                a = validated.a
                b = validated.b
                c = validated.c
            except (json.JSONDecodeError, ValueError):
                # Final fallback to default values
                a = 1 if a is None else a
                b = 0 if b is None else b
                c = 0 if c is None else c
        
        # Ensure we have valid integer coefficients
        a = a if a is not None else 1
        b = b if b is not None else 0
        c = c if c is not None else 0
        
        # Return the function call structure as specified in the output schema
        return {
            "solve_quadratic": {
                "a": int(a),
                "b": int(b),
                "c": int(c)
            }
        }
        
    except Exception as e:
        # Error fallback - return default coefficients
        return {
            "solve_quadratic": {
                "a": 1,
                "b": 0,
                "c": 0
            }
        }