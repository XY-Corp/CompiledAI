from typing import Any, Dict, List, Optional
import json
from pydantic import BaseModel

async def classify_support_ticket(
    ticket_text: str,
    categories: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> str:
    """Classify the support ticket text into one of the predefined categories using LLM semantic analysis.
    
    Args:
        ticket_text: The complete support ticket text content that needs to be categorized
        categories: List of valid category options for classification (billing, technical, account, general)
    
    Returns:
        str: The classified support ticket category as a lowercase string
    """
    try:
        # Handle JSON string input defensively
        if isinstance(categories, str):
            categories = json.loads(categories)
        
        if not isinstance(categories, list):
            return "general"  # Default fallback
            
        if not ticket_text or not ticket_text.strip():
            return "general"  # Default for empty tickets
        
        # Create a clear prompt for LLM classification
        categories_list = ", ".join(categories)
        prompt = f"""Classify this support ticket into exactly one of these categories: {categories_list}

Support Ticket:
{ticket_text.strip()}

Instructions:
- Read the ticket content carefully
- Choose the single most appropriate category
- Return ONLY the category name in lowercase
- billing: payment issues, charges, refunds, subscription problems
- technical: bugs, errors, system issues, feature problems  
- account: login issues, password resets, profile changes
- general: all other inquiries

Category:"""

        # Use LLM for semantic classification (this requires AI understanding)
        response = llm_client.generate(prompt)
        
        # Extract and validate the classification
        classification = response.content.strip().lower()
        
        # Ensure the classification is in our valid categories
        valid_categories = [cat.lower() for cat in categories]
        if classification in valid_categories:
            return classification
        else:
            # Try to find a partial match
            for category in valid_categories:
                if category in classification:
                    return category
            
            # Default fallback
            return "general"
            
    except Exception as e:
        # Fallback to general category on any error
        return "general"