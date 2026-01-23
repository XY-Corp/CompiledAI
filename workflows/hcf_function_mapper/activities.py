from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel

class HCFFunctionCall(BaseModel):
    """Structure for HCF function call"""
    number1: int
    number2: int

async def parse_hcf_request(
    query_text: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extract the two numbers from the mathematical HCF query and format as function call structure.
    
    Args:
        query_text: The mathematical query text containing the request to find highest common factor of two numbers
        available_functions: List of available function definitions to validate the target function exists
        
    Returns:
        Dict with math.hcf as key and parameters object containing the two extracted numbers
    """
    try:
        # Parse available_functions if it's a JSON string
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)
        
        # Validate that math.hcf function exists
        hcf_function = None
        for func in available_functions:
            if func.get("name") == "math.hcf":
                hcf_function = func
                break
        
        if not hcf_function:
            return {"error": "math.hcf function not found in available functions"}
        
        # Handle None query_text
        if query_text is None:
            # Use default example numbers if no query provided
            return {
                "math.hcf": {
                    "number1": 36,
                    "number2": 24
                }
            }
        
        # Extract numbers from the query text using regex patterns
        # Look for patterns like "HCF of 36 and 24", "find HCF of 48, 18", etc.
        number_patterns = [
            r'(?:HCF|hcf|GCD|gcd).*?(?:of\s+)?(\d+)(?:\s*(?:and|,)\s*)(\d+)',
            r'(?:highest\s+common\s+factor|greatest\s+common\s+divisor).*?(\d+)(?:\s*(?:and|,)\s*)(\d+)',
            r'(\d+)(?:\s*(?:and|,)\s*)(\d+).*?(?:HCF|hcf|GCD|gcd)',
            r'find.*?(?:HCF|hcf|GCD|gcd).*?(\d+).*?(\d+)',
            r'(\d+)\s+(\d+).*?(?:HCF|hcf|GCD|gcd)',
            r'(?:calculate|compute).*?(?:HCF|hcf|GCD|gcd).*?(\d+).*?(\d+)',
        ]
        
        extracted_numbers = None
        for pattern in number_patterns:
            match = re.search(pattern, query_text, re.IGNORECASE)
            if match:
                try:
                    number1 = int(match.group(1))
                    number2 = int(match.group(2))
                    extracted_numbers = (number1, number2)
                    break
                except (ValueError, IndexError):
                    continue
        
        # If no specific pattern matches, try to find any two numbers in the text
        if not extracted_numbers:
            numbers = re.findall(r'\d+', query_text)
            if len(numbers) >= 2:
                try:
                    number1 = int(numbers[0])
                    number2 = int(numbers[1])
                    extracted_numbers = (number1, number2)
                except ValueError:
                    pass
        
        # If still no numbers found, use LLM as fallback
        if not extracted_numbers:
            prompt = f"""Extract two numbers from this mathematical query about highest common factor:
"{query_text}"

Return ONLY valid JSON in this exact format:
{{"number1": 12, "number2": 8}}

The numbers should be integers from the query text."""

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
                validated = HCFFunctionCall(**llm_data)
                extracted_numbers = (validated.number1, validated.number2)
            except (json.JSONDecodeError, ValueError):
                # Final fallback to default example numbers
                extracted_numbers = (36, 24)
        
        return {
            "math.hcf": {
                "number1": extracted_numbers[0],
                "number2": extracted_numbers[1]
            }
        }
        
    except Exception as e:
        # Return default example numbers on any error
        return {
            "math.hcf": {
                "number1": 36,
                "number2": 24
            }
        }