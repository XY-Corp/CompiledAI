from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel


class QuadraticParams(BaseModel):
    """Define the expected structure for quadratic function parameters."""
    a: int
    b: int
    c: int
    root_type: str = "all"


async def parse_quadratic_query(
    query_text: str,
    available_functions: str,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Parse the user query to extract quadratic equation coefficients (a, b, c) and determine the appropriate root type parameter."""
    
    try:
        # Handle JSON string input defensively
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)
        
        # Extract coefficients using regex patterns
        # Look for patterns like "a = 3", "a=3", "coefficients a = 3, b = -11, c = -4"
        a_match = re.search(r'a\s*=\s*(-?\d+)', query_text, re.IGNORECASE)
        b_match = re.search(r'b\s*=\s*(-?\d+)', query_text, re.IGNORECASE)
        c_match = re.search(r'c\s*=\s*(-?\d+)', query_text, re.IGNORECASE)
        
        # Extract coefficients or default to 0 if not found
        a = int(a_match.group(1)) if a_match else 0
        b = int(b_match.group(1)) if b_match else 0
        c = int(c_match.group(1)) if c_match else 0
        
        # Determine root_type based on query text
        root_type = "all"  # default
        
        # Check for specific root type requests
        if re.search(r'\breal\s+roots?\b', query_text, re.IGNORECASE):
            root_type = "real"
        elif re.search(r'\bcomplex\s+roots?\b', query_text, re.IGNORECASE):
            root_type = "complex"
        elif re.search(r'\bimaginary\s+roots?\b', query_text, re.IGNORECASE):
            root_type = "complex"
        elif re.search(r'\ball\s+roots?\b', query_text, re.IGNORECASE):
            root_type = "all"
        
        # Create the quadratic function call structure
        quadratic_call = {
            "solve_quadratic": {
                "a": a,
                "b": b,
                "c": c,
                "root_type": root_type
            }
        }
        
        return quadratic_call
        
    except json.JSONDecodeError as e:
        return {"solve_quadratic": {"a": 0, "b": 0, "c": 0, "root_type": "all"}}
    except Exception as e:
        # Fallback: try to extract numbers from the query using any pattern
        numbers = re.findall(r'-?\d+', query_text)
        if len(numbers) >= 3:
            return {
                "solve_quadratic": {
                    "a": int(numbers[0]),
                    "b": int(numbers[1]),
                    "c": int(numbers[2]),
                    "root_type": "all"
                }
            }
        return {"solve_quadratic": {"a": 0, "b": 0, "c": 0, "root_type": "all"}}