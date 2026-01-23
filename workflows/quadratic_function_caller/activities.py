from typing import Any, Dict, List, Optional
import re
import json


async def parse_quadratic_coefficients(
    text: str,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extract quadratic equation coefficients (a, b, c) and root type from natural language text using regex patterns and text parsing."""
    
    try:
        # Initialize default values
        a, b, c = 0, 0, 0
        root_type = "all"  # Default to all roots
        
        # Extract coefficients using regex patterns
        # Pattern for "a = 3", "a=3", "a is 3", etc.
        a_match = re.search(r'a\s*(?:=|is)\s*(-?\d+)', text, re.IGNORECASE)
        if a_match:
            a = int(a_match.group(1))
        
        b_match = re.search(r'b\s*(?:=|is)\s*(-?\d+)', text, re.IGNORECASE)
        if b_match:
            b = int(b_match.group(1))
            
        c_match = re.search(r'c\s*(?:=|is)\s*(-?\d+)', text, re.IGNORECASE)
        if c_match:
            c = int(c_match.group(1))
        
        # Check for root type preferences
        if re.search(r'\b(real\s+roots?|only\s+real|real\s+solutions?)\b', text, re.IGNORECASE):
            root_type = "real"
        elif re.search(r'\b(all\s+roots?|all\s+solutions?|both\s+real\s+and\s+complex)\b', text, re.IGNORECASE):
            root_type = "all"
        
        # Alternative patterns for coefficient extraction
        # Pattern like "3x^2 - 11x - 4"
        if a == 0 and b == 0 and c == 0:
            quadratic_pattern = re.search(r'(-?\d*)\s*x\^?2\s*([+-]\s*\d*)\s*x\s*([+-]\s*\d+)', text, re.IGNORECASE)
            if quadratic_pattern:
                # Extract coefficient a
                a_coeff = quadratic_pattern.group(1)
                if a_coeff == '' or a_coeff == '+':
                    a = 1
                elif a_coeff == '-':
                    a = -1
                else:
                    a = int(a_coeff)
                
                # Extract coefficient b
                b_coeff = quadratic_pattern.group(2).replace(' ', '')
                if b_coeff == '+' or b_coeff == '':
                    b = 1
                elif b_coeff == '-':
                    b = -1
                else:
                    b = int(b_coeff)
                
                # Extract coefficient c
                c_coeff = quadratic_pattern.group(3).replace(' ', '')
                c = int(c_coeff)
        
        return {
            "a": a,
            "b": b,
            "c": c,
            "root_type": root_type
        }
        
    except Exception as e:
        # Return default values if parsing fails
        return {
            "a": 0,
            "b": 0,
            "c": 0,
            "root_type": "all"
        }


async def generate_function_call(
    coefficients_data: dict,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> list[dict[str, Any]]:
    """Generate the required function call JSON structure with extracted coefficients formatted as arrays."""
    
    try:
        # Handle JSON string input defensively
        if isinstance(coefficients_data, str):
            coefficients_data = json.loads(coefficients_data)
        
        # Validate input is a dict
        if not isinstance(coefficients_data, dict):
            return [{"error": f"coefficients_data must be dict, got {type(coefficients_data).__name__}"}]
        
        # Extract coefficients with defaults
        a = coefficients_data.get("a", 0)
        b = coefficients_data.get("b", 0)
        c = coefficients_data.get("c", 0)
        root_type = coefficients_data.get("root_type", "all")
        
        # Generate function call structure with single-element arrays
        function_call = {
            "solve_quadratic": {
                "a": [a],
                "b": [b],
                "c": [c],
                "root_type": [root_type]
            }
        }
        
        return [function_call]
        
    except json.JSONDecodeError as e:
        return [{"error": f"Invalid JSON: {e}"}]
    except Exception as e:
        return [{"error": f"Failed to generate function call: {e}"}]