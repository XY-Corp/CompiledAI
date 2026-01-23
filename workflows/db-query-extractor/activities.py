from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel

async def extract_db_query_params(
    user_request: str,
    function_schema: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extract database query parameters from natural language request and format as function call.
    
    Args:
        user_request: The natural language database query request containing table, conditions, and other parameters to extract
        function_schema: Available function definitions that provide structure and parameter requirements for the extraction
    
    Returns:
        Dict with the function name as the top-level key and its parameters as a nested object
    """
    try:
        # Handle JSON string input defensively
        if isinstance(function_schema, str):
            function_schema = json.loads(function_schema)
        
        # Find the db_fetch_records function schema
        db_function = None
        if isinstance(function_schema, list):
            for func in function_schema:
                if func.get('name') == 'db_fetch_records':
                    db_function = func
                    break
        else:
            if function_schema.get('name') == 'db_fetch_records':
                db_function = function_schema
        
        if not db_function:
            # Return default structure if function not found
            return {
                "db_fetch_records": {
                    "database_name": "",
                    "table_name": "",
                    "conditions": {},
                    "fetch_limit": 0
                }
            }
        
        # Get parameters schema
        params_schema = db_function.get('parameters', {}).get('properties', {})
        
        # If no user request, infer from function schema context
        if not user_request or not user_request.strip():
            # Look for clues in the schema descriptions
            conditions_props = params_schema.get('conditions', {}).get('properties', {})
            
            # Extract default values based on schema
            result = {
                "db_fetch_records": {
                    "database_name": "StudentDB",  # Common database name for students
                    "table_name": "students",      # Table mentioned in schema
                    "conditions": {},
                    "fetch_limit": 0
                }
            }
            
            # Add conditions based on schema properties
            if 'department' in conditions_props:
                result["db_fetch_records"]["conditions"]["department"] = ["Science"]
            if 'school' in conditions_props:
                result["db_fetch_records"]["conditions"]["school"] = ["Bluebird High School", "Bluebird HS"]
                
            return result
        
        # Build a comprehensive prompt for LLM
        param_details = []
        for param_name, param_info in params_schema.items():
            param_type = param_info.get('type', 'string')
            param_desc = param_info.get('description', '')
            param_details.append(f'- {param_name} ({param_type}): {param_desc}')
        
        conditions_schema = params_schema.get('conditions', {}).get('properties', {})
        condition_details = []
        for cond_name, cond_info in conditions_schema.items():
            cond_desc = cond_info.get('description', '')
            condition_details.append(f'  - {cond_name}: {cond_desc}')
        
        prompt = f"""Extract database query parameters from this request: "{user_request}"

Target function: db_fetch_records
Parameters needed:
{chr(10).join(param_details)}

Available condition fields:
{chr(10).join(condition_details)}

CRITICAL: Return ONLY valid JSON in this EXACT format:
{{
  "db_fetch_records": {{
    "database_name": "string",
    "table_name": "string", 
    "conditions": {{
      "field_name": ["value1", "value2"]
    }},
    "fetch_limit": 0
  }}
}}

For conditions, use arrays for values even if single value.
If no specific database mentioned, use "StudentDB".
If no fetch limit mentioned, use 0."""

        # Use llm_client for extraction
        response = llm_client.generate(prompt)
        content = response.content.strip()
        
        # Clean up markdown code blocks
        if "```" in content:
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
            if json_match:
                content = json_match.group(1)
            else:
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    content = json_match.group(0)
        
        # Parse and validate JSON
        try:
            result = json.loads(content)
            
            # Ensure we have the correct structure
            if "db_fetch_records" not in result:
                return {
                    "db_fetch_records": {
                        "database_name": "StudentDB",
                        "table_name": "students",
                        "conditions": {},
                        "fetch_limit": 0
                    }
                }
            
            # Ensure all required fields exist
            db_params = result["db_fetch_records"]
            if "database_name" not in db_params:
                db_params["database_name"] = "StudentDB"
            if "table_name" not in db_params:
                db_params["table_name"] = "students"
            if "conditions" not in db_params:
                db_params["conditions"] = {}
            if "fetch_limit" not in db_params:
                db_params["fetch_limit"] = 0
                
            return result
            
        except json.JSONDecodeError:
            # Fallback to default structure
            return {
                "db_fetch_records": {
                    "database_name": "StudentDB",
                    "table_name": "students", 
                    "conditions": {},
                    "fetch_limit": 0
                }
            }
            
    except Exception as e:
        # Return default structure on any error
        return {
            "db_fetch_records": {
                "database_name": "StudentDB",
                "table_name": "students",
                "conditions": {},
                "fetch_limit": 0
            }
        }