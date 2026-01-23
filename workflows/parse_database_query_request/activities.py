from typing import Any, Dict, List, Optional
import asyncio
import json
import re
from pydantic import BaseModel

class DatabaseCondition(BaseModel):
    """Represents a database query condition."""
    field: str
    operation: str
    value: str

class DatabaseQuery(BaseModel):
    """Represents a structured database query."""
    table: str
    conditions: List[Dict[str, Any]]

async def parse_database_query_request(
    query_text: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Parse natural language database query request and extract structured parameters for database.query function call.
    
    Args:
        query_text: The natural language database query request text that needs to be parsed into structured parameters
        available_functions: List of available database function definitions for context and validation
    
    Returns:
        Dict containing database.query with table and conditions parameters
    """
    try:
        # Handle JSON string input defensively
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)
        
        # Validate we have query text
        if not query_text or not query_text.strip():
            # Return correct structure even for empty query
            return {
                "database.query": {
                    "table": "",
                    "conditions": []
                }
            }
        
        # Find database.query function in the available functions
        db_function = None
        for func in available_functions:
            if func.get('name') == 'database.query':
                db_function = func
                break
        
        if not db_function:
            # Return empty structure if no database.query function found
            return {
                "database.query": {
                    "table": "",
                    "conditions": []
                }
            }
        
        # Extract schema information
        params_schema = db_function.get('parameters', {})
        
        # Create structured prompt for LLM with exact parameter format
        prompt = f"""Parse this natural language database query into structured parameters:

Query: "{query_text}"

Extract:
1. Table name (string)
2. Conditions array with objects containing:
   - field: column name (string)
   - operation: operator like "=", ">", "<", ">=", "<=", "LIKE" (string)  
   - value: comparison value (string)

Examples:
- "Find users older than 25" -> table: "users", conditions: [{{"field": "age", "operation": ">", "value": "25"}}]
- "Get engineers with salary over 50000" -> table: "employees", conditions: [{{"field": "job", "operation": "=", "value": "engineer"}}, {{"field": "salary", "operation": ">", "value": "50000"}}]

Return ONLY valid JSON in this exact format:
{{"table": "table_name", "conditions": [{{"field": "column_name", "operation": "operator", "value": "value"}}]}}"""

        response = llm_client.generate(prompt)
        
        # Extract JSON from response (handles markdown code blocks)
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
        
        # Parse and validate with Pydantic
        try:
            data = json.loads(content)
            validated = DatabaseQuery(**data)
            
            # Return in the required format
            return {
                "database.query": validated.model_dump()
            }
            
        except (json.JSONDecodeError, ValueError) as e:
            # Fallback: try to extract table and conditions with regex
            table_match = re.search(r'\b(?:from|table|in)\s+(\w+)', query_text, re.IGNORECASE)
            table = table_match.group(1) if table_match else ""
            
            conditions = []
            
            # Look for common patterns
            age_match = re.search(r'(?:age|older|younger).+?(\d+)', query_text, re.IGNORECASE)
            if age_match:
                op = ">" if "older" in query_text.lower() or "above" in query_text.lower() else "<"
                conditions.append({
                    "field": "age",
                    "operation": op,
                    "value": age_match.group(1)
                })
            
            job_match = re.search(r'(?:job|work|profession|occupation).+?(\w+)', query_text, re.IGNORECASE)
            if job_match:
                conditions.append({
                    "field": "job", 
                    "operation": "=",
                    "value": job_match.group(1)
                })
            
            salary_match = re.search(r'(?:salary|pay|wage|earn).+?(\d+)', query_text, re.IGNORECASE)
            if salary_match:
                op = ">" if "over" in query_text.lower() or "above" in query_text.lower() else "<"
                conditions.append({
                    "field": "salary",
                    "operation": op, 
                    "value": salary_match.group(1)
                })
            
            return {
                "database.query": {
                    "table": table,
                    "conditions": conditions
                }
            }
            
    except Exception as e:
        # Return empty structure on any error
        return {
            "database.query": {
                "table": "",
                "conditions": []
            }
        }