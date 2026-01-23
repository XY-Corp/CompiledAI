from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel


async def extract_quadratic_parameters(
    prompt_text: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Parse the natural language prompt to extract quadratic equation coefficients (a, b, c) and determine root type requirements, then format as function call structure."""
    try:
        # Handle defensive input parsing
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)
        
        if not isinstance(available_functions, list):
            return {"error": f"available_functions must be list, got {type(available_functions).__name__}"}
        
        # Default values
        a, b, c = 1, 0, 0
        root_type = "all"  # Default to all roots
        
        if prompt_text:
            # Pattern 1: Standard form like "3x^2 - 11x - 4", "2x² + 6x + 5"
            # Handle various formats: x^2, x², x2
            pattern1 = r'(-?\d*)\s*x\^?2?²?\s*([+-]\s*\d+)\s*x\s*([+-]\s*\d+)'
            match1 = re.search(pattern1, prompt_text.replace(' ', ''))
            
            # Pattern 2: Explicit coefficient assignment like "a=3, b=-11, c=-4"
            a_match = re.search(r'a\s*=\s*(-?\d+)', prompt_text)
            b_match = re.search(r'b\s*=\s*(-?\d+)', prompt_text)
            c_match = re.search(r'c\s*=\s*(-?\d+)', prompt_text)
            
            # Pattern 3: Quadratic equation format like "3x² - 11x - 4 = 0"
            pattern3 = r'(-?\d*)\s*x\^?2?²?\s*([+-]\s*\d+)\s*x\s*([+-]\s*\d+)\s*=\s*0'
            match3 = re.search(pattern3, prompt_text.replace(' ', ''))
            
            if match1 or match3:
                match = match1 or match3
                # Parse coefficient a
                a_str = match.group(1)
                if a_str == '' or a_str == '+':
                    a = 1
                elif a_str == '-':
                    a = -1
                else:
                    a = int(a_str)
                
                # Parse coefficient b
                b_str = match.group(2).replace(' ', '').replace('+', '')
                b = int(b_str)
                
                # Parse coefficient c
                c_str = match.group(3).replace(' ', '').replace('+', '')
                c = int(c_str)
                
            elif a_match and b_match and c_match:
                # Parse explicit assignments
                a = int(a_match.group(1))
                b = int(b_match.group(1))
                c = int(c_match.group(1))
            else:
                # Try to extract using LLM for complex cases
                class QuadraticParams(BaseModel):
                    a: int
                    b: int
                    c: int
                    root_type: str = "all"
                
                prompt = f"""Extract the quadratic equation coefficients from this text: "{prompt_text}"
                
A quadratic equation has the form ax² + bx + c = 0 or ax^2 + bx + c = 0.
Find the values of a, b, and c.

If the text mentions "real roots only" or "real solutions only", set root_type to "real".
Otherwise, set root_type to "all".

Return ONLY valid JSON in this exact format:
{{"a": 1, "b": 0, "c": 0, "root_type": "all"}}"""

                response = llm_client.generate(prompt)
                
                # Extract JSON from response
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
                    data = json.loads(content)
                    validated = QuadraticParams(**data)
                    a = validated.a
                    b = validated.b
                    c = validated.c
                    root_type = validated.root_type
                except (json.JSONDecodeError, ValueError):
                    # Fallback: try to find numbers in the text
                    numbers = re.findall(r'-?\d+', prompt_text)
                    if len(numbers) >= 3:
                        a = int(numbers[0])
                        b = int(numbers[1])
                        c = int(numbers[2])
            
            # Determine root type from text
            if "real" in prompt_text.lower() and ("only" in prompt_text.lower() or "roots" in prompt_text.lower()):
                root_type = "real"
        
        # Return the function call structure
        return {
            "solve_quadratic": {
                "a": a,
                "b": b,
                "c": c,
                "root_type": root_type
            }
        }
        
    except Exception as e:
        return {"error": f"Failed to extract quadratic parameters: {str(e)}"}