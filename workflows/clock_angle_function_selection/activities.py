from typing import Any, Dict, List, Optional
import asyncio
import json
import re
from pydantic import BaseModel


class ClockFunctionCall(BaseModel):
    """Define the expected function call structure."""
    calculate_clock_angle: Dict[str, Any]


async def analyze_clock_query(
    user_query: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Analyzes a clock time question to extract the time components and determine the appropriate function to call.
    
    Args:
        user_query: The complete user question about clock time
        available_functions: List of available function definitions that can be selected from
    
    Returns:
        Dict with function call structure containing calculate_clock_angle with hours, minutes, and round_to parameters
    """
    try:
        # Handle JSON string input defensively
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)
        
        if not isinstance(available_functions, list):
            return {"error": f"available_functions must be list, got {type(available_functions).__name__}"}
        
        if not user_query or not user_query.strip():
            return {"error": "user_query is required"}
        
        # First try to extract time using regex patterns from the user query
        time_patterns = [
            r'(?:at )?(\d{1,2}):(\d{2})\s*(?:[APap][Mm])?',  # 6:30 PM, 6:30
            r'(?:at )?(\d{1,2})\s*(?:[APap][Mm])',  # 6 PM
            r'(\d{1,2}):(\d{2})',  # 6:30
            r'(\d{1,2})\s+(?:o\'?clock)?',  # 6 o'clock
        ]
        
        hours = None
        minutes = 0
        
        for pattern in time_patterns:
            match = re.search(pattern, user_query)
            if match:
                hours = int(match.group(1))
                if len(match.groups()) > 1 and match.group(2):
                    minutes = int(match.group(2))
                break
        
        # If regex fails, use LLM to extract time components
        if hours is None:
            prompt = f"""Extract the time from this clock question: "{user_query}"
            
Return ONLY valid JSON in this exact format:
{{"hours": 6, "minutes": 30}}

If PM is mentioned and hour is less than 12, convert to 24-hour format (add 12).
If no minutes are specified, use 0.
Examples:
- "6:30 PM" -> {{"hours": 18, "minutes": 30}}
- "3 o'clock" -> {{"hours": 3, "minutes": 0}}
- "12:45" -> {{"hours": 12, "minutes": 45}}"""
            
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
                time_data = json.loads(content)
                hours = int(time_data.get('hours', 0))
                minutes = int(time_data.get('minutes', 0))
            except (json.JSONDecodeError, ValueError, KeyError):
                return {"error": "Failed to extract time from query"}
        
        # Handle PM conversion if not already done
        if 'pm' in user_query.lower() and hours < 12:
            hours += 12
        
        # Validate time values
        if hours < 0 or hours > 23:
            hours = hours % 24
        if minutes < 0 or minutes > 59:
            minutes = 0
        
        # Find calculate_clock_angle function in available functions
        clock_function = None
        for func in available_functions:
            if func.get('name') == 'calculate_clock_angle':
                clock_function = func
                break
        
        if not clock_function:
            return {"error": "calculate_clock_angle function not found in available functions"}
        
        # Build the function call parameters
        params = {
            "hours": hours,
            "minutes": minutes
        }
        
        # Check if round_to is a parameter and add default if needed
        func_params = clock_function.get('parameters', {})
        if isinstance(func_params, dict):
            properties = func_params.get('properties', {})
            if 'round_to' in properties:
                params['round_to'] = 2  # Default rounding to 2 decimal places
        
        # Return the expected structure
        result = {
            "calculate_clock_angle": params
        }
        
        return result
        
    except Exception as e:
        return {"error": f"Failed to analyze clock query: {str(e)}"}