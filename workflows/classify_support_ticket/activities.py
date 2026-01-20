from typing import Any, Dict, List, Optional
import asyncio
import json
import re
from pydantic import BaseModel


class TicketClassification(BaseModel):
    """Schema for ticket classification result."""
    category: str


async def classify_ticket_category(
    ticket_text: str,
    categories: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> str:
    """Classifies the support ticket text into one of four categories using semantic analysis.
    
    Args:
        ticket_text: The complete support ticket text content that needs to be analyzed and classified into a category
        categories: List of valid category options that the ticket can be classified into
        
    Returns:
        str: The single support ticket category classification as a string - one of: billing, technical, account, or general
    """
    try:
        # Handle defensive parsing for categories if it comes as JSON string
        if isinstance(categories, str):
            categories = json.loads(categories)
        
        # Validate that categories is a list
        if not isinstance(categories, list):
            return "general"  # fallback to general category
        
        # Clean the ticket text
        cleaned_text = ticket_text.strip()
        if not cleaned_text:
            return "general"  # fallback for empty text
        
        # Create a clear classification prompt
        categories_text = ", ".join(categories)
        prompt = f"""Classify this support ticket into exactly ONE of these categories: {categories_text}

Support ticket text:
{cleaned_text}

Categories:
- billing: Payment issues, charges, refunds, subscription problems, billing inquiries
- technical: Software bugs, system errors, feature not working, performance issues, integrations
- account: Login problems, password reset, user permissions, account settings, profile issues  
- general: Questions, feedback, requests that don't fit other categories

Return ONLY the category name (one word): billing, technical, account, or general"""

        # Use LLM for semantic classification
        response = llm_client.generate(prompt)
        
        # Clean and validate the response
        classification = response.content.strip().lower()
        
        # Validate the classification is in our allowed categories
        valid_categories = [cat.lower() for cat in categories]
        if classification in valid_categories:
            return classification
        
        # If LLM returned invalid category, try to map common variations
        classification_mapping = {
            "payment": "billing",
            "charge": "billing", 
            "money": "billing",
            "subscription": "billing",
            "refund": "billing",
            "bug": "technical",
            "error": "technical",
            "broken": "technical",
            "not working": "technical",
            "login": "account",
            "password": "account",
            "access": "account",
            "profile": "account",
            "user": "account"
        }
        
        # Check if any mapping keywords appear in the classification
        for keyword, category in classification_mapping.items():
            if keyword in classification and category in valid_categories:
                return category
                
        # Final fallback - return general if nothing else matches
        return "general"
        
    except Exception as e:
        # Return general category as safe fallback on any error
        return "general"