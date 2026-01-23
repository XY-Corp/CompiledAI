from typing import Any, Dict, List, Optional
import asyncio
import json
import re


async def parse_quadratic_request(
    prompt: str,
    functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Parse the user prompt to extract quadratic equation coefficients and any optional parameters,
    then build a function call structure with solve_quadratic as the top-level key.
    
    Args:
        prompt: The natural language request containing quadratic equation coefficients (a, b, c) 
                and possibly root type preference
        functions: List of available function definitions with their parameter schemas for reference
        
    Returns:
        Function call object with solve_quadratic as the top-level key containing the parameters.
        Example: {"solve_quadratic": {"a": 3, "b": -11, "c": -4, "root_type": "all"}}
    """
    try:
        # Handle JSON string input defensively
        if isinstance(functions, str):
            functions = json.loads(functions)
        
        # Determine root_type from prompt - default to 'all' as per description
        root_type = "all"
        prompt_lower = prompt.lower()
        
        # Only set to 'real' if explicitly mentioned
        if 'real' in prompt_lower and ('only' in prompt_lower or 'just' in prompt_lower or 'real roots' in prompt_lower):
            root_type = "real"
        # Confirm 'all' if explicitly mentioned
        if 'all' in prompt_lower or 'complex' in prompt_lower or 'both' in prompt_lower:
            root_type = "all"
        
        # Try multiple regex patterns to extract coefficients
        
        # Pattern 1: Explicit coefficient assignment like "a=3, b=-11, c=-4" or "a: 3, b: -11, c: -4"
        coeff_pattern = r'a\s*[=:]\s*(-?\d+).*?b\s*[=:]\s*(-?\d+).*?c\s*[=:]\s*(-?\d+)'
        match = re.search(coeff_pattern, prompt, re.IGNORECASE | re.DOTALL)
        
        if match:
            a, b, c = map(int, match.groups())
            return {
                "solve_quadratic": {
                    "a": a,
                    "b": b,
                    "c": c,
                    "root_type": root_type
                }
            }
        
        # Pattern 2: Standard quadratic form like "3x² - 11x - 4" or "3x^2 - 11x - 4"
        # Normalize the text first
        normalized = prompt.replace('²', '^2').replace('**2', '^2')
        
        # Match patterns like "3x^2 - 11x - 4" with optional spaces and signs
        quad_pattern = r'(-?\d*)\s*x\s*\^?\s*2\s*([+-])\s*(\d*)\s*x\s*([+-])\s*(\d+)'
        match = re.search(quad_pattern, normalized)
        
        if match:
            a_str, b_sign, b_str, c_sign, c_str = match.groups()
            
            # Parse coefficient a
            a = int(a_str) if a_str and a_str not in ['', '+', '-'] else (1 if a_str != '-' else -1)
            
            # Parse coefficient b with sign
            b_val = int(b_str) if b_str and b_str not in ['', '+', '-'] else 1
            b = b_val if b_sign == '+' else -b_val
            
            # Parse coefficient c with sign
            c_val = int(c_str) if c_str else 0
            c = c_val if c_sign == '+' else -c_val
            
            return {
                "solve_quadratic": {
                    "a": a,
                    "b": b,
                    "c": c,
                    "root_type": root_type
                }
            }
        
        # Pattern 3: Coefficients mentioned in context like "coefficients 3, -11, -4" or "a, b, c are 3, -11, -4"
        coeff_list_pattern = r'coefficients?\s*(?:are|:)?\s*(-?\d+)\s*,\s*(-?\d+)\s*,\s*(-?\d+)'
        match = re.search(coeff_list_pattern, prompt, re.IGNORECASE)
        
        if match:
            a, b, c = map(int, match.groups())
            return {
                "solve_quadratic": {
                    "a": a,
                    "b": b,
                    "c": c,
                    "root_type": root_type
                }
            }
        
        # Pattern 4: Look for three consecutive numbers that could be a, b, c
        # This handles cases like "solve for 3, -11, -4" or just numbers in sequence
        numbers = re.findall(r'-?\d+', prompt)
        if len(numbers) >= 3:
            # Take first three numbers as a, b, c
            a, b, c = map(int, numbers[:3])
            return {
                "solve_quadratic": {
                    "a": a,
                    "b": b,
                    "c": c,
                    "root_type": root_type
                }
            }
        
        # If regex patterns fail, use LLM as fallback
        llm_prompt = f"""Extract the quadratic equation coefficients (a, b, c) from this text:

"{prompt}"

A quadratic equation is in the form: ax² + bx + c = 0

Return ONLY valid JSON in this exact format:
{{"a": <integer>, "b": <integer>, "c": <integer>}}

Example: {{"a": 3, "b": -11, "c": -4}}"""

        response = llm_client.generate(llm_prompt)
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
        
        # Parse the JSON response
        data = json.loads(content)
        
        return {
            "solve_quadratic": {
                "a": int(data.get("a", 0)),
                "b": int(data.get("b", 0)),
                "c": int(data.get("c", 0)),
                "root_type": root_type
            }
        }
        
    except json.JSONDecodeError as e:
        # Return a default structure if parsing fails entirely
        return {
            "solve_quadratic": {
                "a": 0,
                "b": 0,
                "c": 0,
                "root_type": "all"
            }
        }
    except Exception as e:
        return {
            "solve_quadratic": {
                "a": 0,
                "b": 0,
                "c": 0,
                "root_type": "all"
            }
        }
