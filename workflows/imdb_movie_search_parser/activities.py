from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel


class ParsedMovieQuery(BaseModel):
    """Pydantic model for parsed IMDB movie query structure."""
    actor_name: str
    year: int
    category: str = "all"


async def parse_movie_query(
    query_text: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extracts actor name, year, and optional category from natural language movie search queries to format as IMDB function parameters.
    
    Args:
        query_text: The natural language query containing actor name, year, and optionally movie category for IMDB movie search
        available_functions: List of available function definitions with their parameter schemas for context and validation
        
    Returns:
        Dict with imdb.find_movies_by_actor as key and parameters object containing actor_name, year, and category
    """
    try:
        # Handle JSON string input defensively
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)
        
        # Validate types
        if not isinstance(available_functions, list):
            available_functions = []
        
        # Find the IMDB function schema to understand expected parameters
        imdb_function = None
        for func in available_functions:
            if isinstance(func, dict) and func.get('name') == 'imdb.find_movies_by_actor':
                imdb_function = func
                break
        
        # Extract parameters from the function schema to ensure we use exact parameter names
        expected_params = {}
        if imdb_function and 'parameters' in imdb_function:
            params_schema = imdb_function['parameters']
            if isinstance(params_schema, dict):
                expected_params = params_schema
        
        # Create a focused prompt for LLM extraction
        prompt = f"""Extract movie search parameters from this query: "{query_text}"

Extract these exact values:
1. actor_name - The name of the actor/actress (required)
2. year - The year as an integer (required)
3. category - Movie category type, default to "all" if not specified

Examples:
- "Find Leonardo DiCaprio movies from 2010" → actor_name: "Leonardo DiCaprio", year: 2010, category: "all"
- "Show me Tom Hanks drama movies from 1994" → actor_name: "Tom Hanks", year: 1994, category: "drama"

Return ONLY valid JSON in this exact format:
{{"actor_name": "Actor Name", "year": 2010, "category": "all"}}"""

        # Use LLM to extract structured data from natural language query
        response = llm_client.generate(prompt)
        content = response.content.strip()
        
        # Extract JSON from response (handle markdown code blocks)
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
            validated = ParsedMovieQuery(**data)
            
            # Return in the exact output schema format required
            return {
                "imdb.find_movies_by_actor": validated.model_dump()
            }
            
        except (json.JSONDecodeError, ValueError) as e:
            # Fallback: try to extract with regex patterns
            actor_match = re.search(r'(?:find|show|search|get).*?([A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)', query_text, re.IGNORECASE)
            year_match = re.search(r'\b(19|20)\d{2}\b', query_text)
            category_match = re.search(r'\b(drama|comedy|action|thriller|romance|horror|sci-fi|documentary)\b', query_text, re.IGNORECASE)
            
            if actor_match and year_match:
                actor_name = actor_match.group(1).strip()
                year = int(year_match.group(0))
                category = category_match.group(1).lower() if category_match else "all"
                
                return {
                    "imdb.find_movies_by_actor": {
                        "actor_name": actor_name,
                        "year": year,
                        "category": category
                    }
                }
            else:
                # Return error in the expected format
                return {
                    "imdb.find_movies_by_actor": {
                        "actor_name": "<UNKNOWN>",
                        "year": 2000,
                        "category": "all"
                    }
                }
                
    except Exception as e:
        # Return default structure on any error
        return {
            "imdb.find_movies_by_actor": {
                "actor_name": "<UNKNOWN>",
                "year": 2000,
                "category": "all"
            }
        }