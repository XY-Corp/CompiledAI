from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel

class EmployeeFunctionCall(BaseModel):
    """Pydantic model for validating employee.fetch_data function call structure."""
    company_name: str
    employee_id: int
    data_field: List[str]

async def parse_employee_request(
    user_request: str,
    function_schema: dict,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Parse user request to extract company name, employee ID, and data fields for employee.fetch_data function.
    
    Args:
        user_request: The raw user input text containing employee data retrieval request
        function_schema: The available function schema containing parameter definitions
        
    Returns:
        Dict with employee.fetch_data as key and parameters as nested object with extracted values
    """
    try:
        # Handle JSON string input defensively
        if isinstance(function_schema, str):
            function_schema = json.loads(function_schema)
        
        if not user_request:
            return {"error": "user_request is required"}
            
        # Find the employee.fetch_data function schema
        employee_func_schema = None
        if isinstance(function_schema, list):
            for func in function_schema:
                if func.get('name') == 'employee.fetch_data':
                    employee_func_schema = func
                    break
        elif isinstance(function_schema, dict) and function_schema.get('name') == 'employee.fetch_data':
            employee_func_schema = function_schema
            
        if not employee_func_schema:
            return {"error": "employee.fetch_data function not found in schema"}
            
        # Get parameter details from schema
        params = employee_func_schema.get('parameters', {})
        properties = params.get('properties', {})
        
        # Get available data fields from schema enum if available
        data_field_options = []
        if 'data_field' in properties:
            data_field_schema = properties['data_field']
            if 'items' in data_field_schema and 'enum' in data_field_schema['items']:
                data_field_options = data_field_schema['items']['enum']
            else:
                # Default options if not specified in schema
                data_field_options = ["Personal Info", "Job History", "Payroll", "Attendance", "Benefits"]
        
        # Create structured prompt for LLM extraction
        prompt = f"""Extract employee data parameters from this user request:
"{user_request}"

The function employee.fetch_data requires these EXACT parameters:
- company_name: string (name of the company)
- employee_id: integer (numeric ID of the employee)
- data_field: array of strings (data categories to fetch)

Available data field options: {data_field_options}

Return ONLY valid JSON in this exact format:
{{"company_name": "Company Name", "employee_id": 123, "data_field": ["Personal Info", "Job History"]}}

Use the exact parameter names shown above. Extract actual values from the user request."""

        # Use LLM to extract parameters
        response = llm_client.generate(prompt)
        content = response.content.strip()
        
        # Extract JSON from response (handle markdown code blocks)
        if "```" in content:
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
            if json_match:
                content = json_match.group(1)
            else:
                json_match = re.search(r'\{.*?\}', content, re.DOTALL)
                if json_match:
                    content = json_match.group(0)
        
        # Parse and validate with Pydantic
        try:
            data = json.loads(content)
            validated = EmployeeFunctionCall(**data)
            
            # Return in the exact format specified by output schema
            return {
                "employee.fetch_data": validated.model_dump()
            }
            
        except (json.JSONDecodeError, ValueError) as e:
            # Fallback: try to extract with regex patterns
            company_match = re.search(r'(?:company|organization|corp|ltd|inc)[:\s]*([^\n,]+)', user_request, re.IGNORECASE)
            id_match = re.search(r'(?:employee|emp|id)[:\s]*(\d+)', user_request, re.IGNORECASE)
            
            company_name = company_match.group(1).strip() if company_match else "Unknown Company"
            employee_id = int(id_match.group(1)) if id_match else 0
            
            # Extract data fields by matching against available options
            data_fields = []
            for option in data_field_options:
                if option.lower().replace(" ", "") in user_request.lower().replace(" ", ""):
                    data_fields.append(option)
            
            # Default to Personal Info if none found
            if not data_fields:
                data_fields = ["Personal Info"]
            
            return {
                "employee.fetch_data": {
                    "company_name": company_name,
                    "employee_id": employee_id,
                    "data_field": data_fields
                }
            }
        
    except json.JSONDecodeError as e:
        return {"error": f"Invalid JSON in function_schema: {e}"}
    except Exception as e:
        return {"error": f"Failed to parse employee request: {e}"}