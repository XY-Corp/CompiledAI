from typing import Any, Dict, List, Optional
import asyncio
import json
import re
from pydantic import BaseModel

class FunctionCall(BaseModel):
    """Expected structure for the function call response."""
    calculate_molecular_weight: Dict[str, str]

async def extract_function_parameters(
    query_text: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extract function name and parameters from natural language molecular weight calculation query.
    
    Args:
        query_text: The natural language query requesting molecular weight calculation with compound formula and unit information
        available_functions: List of available function definitions with their parameter specifications for context
    
    Returns:
        Function call structure with calculate_molecular_weight as the key and parameters object containing compound (molecular formula string) and to_unit (unit string) fields
    """
    try:
        # Handle JSON string input defensively
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)
        
        # Validate inputs
        if not isinstance(available_functions, list):
            return {"calculate_molecular_weight": {"compound": "<UNKNOWN>", "to_unit": "grams/mole"}}
        
        # Format function schema for LLM context
        function_info = ""
        for func in available_functions:
            if func.get('name') == 'calculate_molecular_weight':
                params_schema = func.get('parameters', {})
                function_info = f"Function: {func['name']}\n"
                function_info += f"Description: {func.get('description', '')}\n"
                function_info += "Parameters:\n"
                for param_name, param_info in params_schema.items():
                    if isinstance(param_info, str):
                        param_type = param_info
                    else:
                        param_type = param_info.get('type', 'string')
                    function_info += f"  - {param_name}: {param_type}\n"
                break
        
        # Create focused prompt for parameter extraction
        prompt = f"""Extract molecular weight calculation parameters from this query: "{query_text}"

{function_info}

Extract ONLY:
1. compound: The molecular formula (e.g., "C6H12O6", "H2O", "NaCl")
2. to_unit: The desired unit (e.g., "grams/mole", "kg/mol", "daltons")

If no unit is specified, use "grams/mole" as default.

Return ONLY valid JSON in this exact format:
{{"compound": "molecular_formula", "to_unit": "unit_string"}}

Examples:
- "What is the molecular weight of glucose C6H12O6?" → {{"compound": "C6H12O6", "to_unit": "grams/mole"}}
- "Calculate molecular weight of water H2O in kg/mol" → {{"compound": "H2O", "to_unit": "kg/mol"}}"""

        response = llm_client.generate(prompt)
        content = response.content.strip()
        
        # Extract JSON from response (handles markdown code blocks)
        if "```" in content:
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
            if json_match:
                content = json_match.group(1)
            else:
                json_match = re.search(r'\{.*?\}', content, re.DOTALL)
                if json_match:
                    content = json_match.group(0)
        
        # Parse and validate extracted parameters
        try:
            params_data = json.loads(content)
            
            # Ensure we have the required fields
            compound = params_data.get('compound', '<UNKNOWN>')
            to_unit = params_data.get('to_unit', 'grams/mole')
            
            # Validate compound is not empty
            if not compound or compound.strip() == "":
                compound = "<UNKNOWN>"
                
            # Return in the exact format required by the schema
            return {
                "calculate_molecular_weight": {
                    "compound": compound,
                    "to_unit": to_unit
                }
            }
            
        except (json.JSONDecodeError, ValueError) as e:
            # Fallback: try to extract compound using regex patterns
            compound_match = re.search(r'([A-Z][a-z]?\d*)+', query_text)
            compound = compound_match.group(0) if compound_match else "<UNKNOWN>"
            
            # Look for unit patterns
            unit_patterns = [
                r'(grams?/mole?)',
                r'(kg/mol)',
                r'(daltons?)',
                r'(g/mol)',
                r'(amu)'
            ]
            to_unit = "grams/mole"  # default
            for pattern in unit_patterns:
                unit_match = re.search(pattern, query_text, re.IGNORECASE)
                if unit_match:
                    to_unit = unit_match.group(1).lower()
                    if to_unit in ['gram/mole', 'grams/mole']:
                        to_unit = 'grams/mole'
                    break
            
            return {
                "calculate_molecular_weight": {
                    "compound": compound,
                    "to_unit": to_unit
                }
            }
            
    except Exception as e:
        # Ultimate fallback
        return {
            "calculate_molecular_weight": {
                "compound": "<UNKNOWN>",
                "to_unit": "grams/mole"
            }
        }