from typing import Any, Dict, List, Optional
import json
from pydantic import BaseModel


async def classify_support_ticket(
    ticket_content: str,
    available_categories: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> str:
    """Analyzes the support ticket content using LLM to determine the appropriate category from the predefined list.
    
    Args:
        ticket_content: The complete support ticket text content that needs to be analyzed and classified into a category
        available_categories: List of valid category names that the ticket can be classified into (billing, technical, account, general)
    
    Returns:
        The most appropriate category classification for the support ticket content as a lowercase string
    """
    # Handle JSON string inputs defensively
    if isinstance(available_categories, str):
        try:
            available_categories = json.loads(available_categories)
        except json.JSONDecodeError:
            # If it's not valid JSON, treat as single category
            available_categories = [available_categories]
    
    if not isinstance(available_categories, list):
        available_categories = ["billing", "technical", "account", "general"]
    
    # Ensure categories are lowercase strings
    categories = [str(cat).lower() for cat in available_categories]
    
    # Create classification schema for validation
    class TicketClassification(BaseModel):
        category: str
    
    # Create prompt for LLM classification
    prompt = f"""Classify this support ticket into exactly one of these categories: {', '.join(categories)}

Categories:
- billing: Issues related to payments, charges, refunds, subscription billing
- technical: Technical problems, bugs, software issues, functionality problems
- account: Account access, login issues, profile management, account settings
- general: General inquiries, questions, requests that don't fit other categories

Support Ticket Content:
{ticket_content}

Return ONLY the category name as a single lowercase word from the list above."""

    # Use LLM to classify the ticket
    response = llm_client.generate(prompt)
    
    # Extract and validate the classification
    classification = response.content.strip().lower()
    
    # Ensure the classification is in the available categories
    if classification not in categories:
        # Try to find a partial match or default to general
        for category in categories:
            if category in classification:
                classification = category
                break
        else:
            # If no match found, analyze content with keyword mapping
            content_lower = ticket_content.lower()
            if any(word in content_lower for word in ['charge', 'bill', 'payment', 'refund', 'subscription', 'invoice']):
                classification = 'billing'
            elif any(word in content_lower for word in ['bug', 'error', 'not working', 'broken', 'crash', 'technical']):
                classification = 'technical'
            elif any(word in content_lower for word in ['login', 'password', 'account', 'access', 'profile']):
                classification = 'account'
            else:
                classification = 'general'
    
    # Validate the result using Pydantic
    try:
        validated = TicketClassification(category=classification)
        return validated.category
    except ValueError:
        # Fallback to general if validation fails
        return 'general'