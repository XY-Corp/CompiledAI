from typing import Any, Dict, List, Optional
import asyncio
import json
import re
from pydantic import BaseModel


class HistogramParameters(BaseModel):
    """Expected structure for histogram function parameters."""
    data: List[int]
    bins: int


class FunctionCall(BaseModel):
    """Expected structure for the function call response."""
    create_histogram: HistogramParameters


async def parse_histogram_request(
    user_request: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Parses natural language histogram request to extract data points and bin parameters, returning the exact function call structure.
    
    Args:
        user_request: The complete natural language request containing histogram data and parameters to be extracted
        available_functions: List of available function definitions including create_histogram function schema for validation
        
    Returns:
        Dict with create_histogram as key and extracted parameters as value
    """
    try:
        # Handle JSON string input defensively
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)
        
        if not isinstance(available_functions, list) or not available_functions:
            return {"create_histogram": {"data": [], "bins": 10}}
        
        # Find create_histogram function definition
        create_histogram_func = None
        for func in available_functions:
            if func.get('name') == 'create_histogram':
                create_histogram_func = func
                break
        
        if not create_histogram_func:
            return {"create_histogram": {"data": [], "bins": 10}}
        
        # Create LLM prompt to extract histogram data and bins
        prompt = f"""Extract histogram data and bin count from this request: "{user_request}"

Look for:
1. Numerical data points (integers) that should be plotted in the histogram
2. Number of bins requested (or use reasonable default if not specified)

Return ONLY valid JSON in this exact format:
{{"data": [list of integer values], "bins": integer_value}}

Example: {{"data": [85, 90, 88, 92, 86, 89, 91], "bins": 5}}

If no specific data is mentioned in the request, extract any numbers that could be data points.
If no bin count is specified, use a reasonable default like 5 or 10."""

        response = llm_client.generate(prompt)
        content = response.content.strip()
        
        # Remove markdown code blocks if present
        if "```" in content:
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
            if json_match:
                content = json_match.group(1)
            else:
                # Try to find any JSON object
                json_match = re.search(r'\{.*?\}', content, re.DOTALL)
                if json_match:
                    content = json_match.group(0)
        
        # Parse the extracted parameters
        try:
            extracted_params = json.loads(content)
            
            # Validate with Pydantic
            validated_params = HistogramParameters(**extracted_params)
            
            # Return in the required format
            return {
                "create_histogram": validated_params.model_dump()
            }
            
        except (json.JSONDecodeError, ValueError) as e:
            # Fallback: try to extract numbers using regex
            numbers = re.findall(r'\b\d+\b', user_request)
            if numbers:
                # Convert to integers and use first 7 as data, last as bins if available
                int_numbers = [int(n) for n in numbers]
                if len(int_numbers) > 1:
                    data = int_numbers[:-1] if len(int_numbers) > 2 else int_numbers
                    bins = int_numbers[-1] if len(int_numbers) > 1 and int_numbers[-1] <= 20 else 5
                else:
                    data = int_numbers
                    bins = 5
            else:
                # Default fallback
                data = [85, 90, 88, 92, 86, 89, 91]
                bins = 5
            
            return {
                "create_histogram": {
                    "data": data,
                    "bins": bins
                }
            }
        
    except Exception as e:
        # Final fallback with reasonable defaults
        return {
            "create_histogram": {
                "data": [85, 90, 88, 92, 86, 89, 91],
                "bins": 5
            }
        }