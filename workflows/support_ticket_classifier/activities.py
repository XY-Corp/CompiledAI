from typing import Any, Dict, List, Optional
import json
from pydantic import BaseModel


class TicketClassification(BaseModel):
    """Expected structure for ticket classification."""
    category: str


async def classify_support_ticket(
    ticket_text: str,
    categories: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> str:
    """Classifies the support ticket text into one of four predefined categories using LLM semantic understanding.
    
    Args:
        ticket_text: The complete support ticket text containing the customer's issue or request to be classified
        categories: List of predefined category options for classification: [billing, technical, account, general]
        
    Returns:
        str: The single category name as a string
    """
    try:
        # Handle JSON string input defensively for categories
        if isinstance(categories, str):
            categories = json.loads(categories)
        
        # Validate categories is a list
        if not isinstance(categories, list):
            return "general"  # Default fallback
            
        # Create a clear classification prompt
        categories_text = ", ".join(categories)
        prompt = f"""Classify this support ticket into exactly ONE of these categories: {categories_text}

Support ticket text:
{ticket_text}

Rules:
- billing: issues with payments, charges, invoices, refunds, subscriptions
- technical: software bugs, system errors, integration issues, performance problems
- account: login problems, password resets, profile changes, permissions
- general: everything else including questions, feedback, feature requests

Return ONLY the category name as a single word: {categories_text}"""

        # Use LLM for semantic classification
        response = llm_client.generate(prompt)
        
        # Extract and validate the response
        result = response.content.strip().lower()
        
        # Ensure the result is one of the valid categories
        valid_categories = [cat.lower() for cat in categories]
        if result in valid_categories:
            # Return the original case from the categories list
            original_index = valid_categories.index(result)
            return categories[original_index]
        
        # Fallback: try to find partial match
        for i, cat in enumerate(valid_categories):
            if cat in result or result in cat:
                return categories[i]
                
        # Ultimate fallback
        return "general"
        
    except Exception as e:
        # Return safe default on any error
        return "general"