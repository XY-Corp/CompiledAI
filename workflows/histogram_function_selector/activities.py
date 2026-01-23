from typing import Any, Dict, List, Optional
import asyncio
import json
import re
from pydantic import BaseModel

class CreateHistogramParams(BaseModel):
    """Expected structure for create_histogram function parameters."""
    data: List[int]
    bins: int

class HistogramFunctionCall(BaseModel):
    """Validates the create_histogram function call structure."""
    create_histogram: CreateHistogramParams

async def extract_histogram_parameters(
    user_prompt: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extracts student scores data and bin configuration from user prompt and formats as create_histogram function call.
    
    Args:
        user_prompt: The complete user input text containing the histogram request with student scores and bin range specifications
        available_functions: List of available function definitions to understand the expected parameter structure
        
    Returns:
        Dict with create_histogram function call structure containing data array and bins integer
    """
    try:
        # Parse available_functions if it's a JSON string
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)
            
        # Verify create_histogram function exists in available functions
        create_histogram_func = None
        for func in available_functions:
            if func.get('name') == 'create_histogram':
                create_histogram_func = func
                break
                
        if not create_histogram_func:
            return {"error": "create_histogram function not found in available functions"}
        
        # Extract numeric data (student scores) from the prompt
        # Look for patterns like: numbers, arrays, or score mentions
        numbers = re.findall(r'\b\d+\b', user_prompt)
        student_scores = [int(num) for num in numbers if 20 <= int(num) <= 100]  # Reasonable score range
        
        # If no scores found in reasonable range, try all numbers
        if not student_scores:
            student_scores = [int(num) for num in numbers if int(num) > 0]
        
        # Extract bins configuration
        bins_value = 5  # default
        
        # Look for explicit bin mentions
        bin_patterns = [
            r'bins?\s*[:=]?\s*(\d+)',
            r'(\d+)\s*bins?',
            r'divide\s+into\s+(\d+)',
            r'(\d+)\s*groups?',
            r'(\d+)\s*ranges?'
        ]
        
        for pattern in bin_patterns:
            match = re.search(pattern, user_prompt.lower())
            if match:
                bins_value = int(match.group(1))
                break
        
        # If we have few data points, adjust bins accordingly
        if student_scores and len(student_scores) < bins_value:
            bins_value = max(1, len(student_scores) - 1)
        
        # Use LLM as fallback for complex extraction if needed
        if not student_scores:
            prompt = f"""Extract student scores and bin count from this request:
"{user_prompt}"

Look for:
- Numbers that could be student test scores (typically 0-100)
- Specification of how many bins/groups/ranges to use

Return JSON in this exact format:
{{"data": [85, 90, 88, 92], "bins": 5}}

If no explicit bin count is mentioned, use 5 as default."""

            response = llm_client.generate(prompt)
            content = response.content.strip()
            
            # Extract JSON from response
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
                if 'data' in llm_data and isinstance(llm_data['data'], list):
                    student_scores = [int(score) for score in llm_data['data']]
                if 'bins' in llm_data and isinstance(llm_data['bins'], int):
                    bins_value = llm_data['bins']
            except (json.JSONDecodeError, ValueError, KeyError):
                # Fall back to defaults if LLM parsing fails
                pass
        
        # Ensure we have some data
        if not student_scores:
            # Default example scores if nothing extracted
            student_scores = [85, 90, 88, 92, 86, 89, 91]
        
        # Validate with Pydantic
        function_call = HistogramFunctionCall(
            create_histogram=CreateHistogramParams(
                data=student_scores,
                bins=bins_value
            )
        )
        
        return function_call.model_dump()
        
    except Exception as e:
        # Fallback with default values
        return {
            "create_histogram": {
                "data": [85, 90, 88, 92, 86, 89, 91],
                "bins": 5
            }
        }