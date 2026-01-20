from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel


class TicketClassification(BaseModel):
    """Define the expected classification structure."""
    category: str


async def classify_support_ticket(
    ticket_text: str,
    # Injected context (always include)
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> str:
    """Classify support ticket text into one of four categories: billing, technical, account, or general.
    
    Uses semantic analysis to determine the most appropriate category based on ticket content.
    
    Args:
        ticket_text: The complete support ticket text content to be classified
        
    Returns:
        The support ticket category classification as a single string value
        (billing, technical, account, or general)
    """
    try:
        # Handle JSON string input defensively
        if isinstance(ticket_text, str) and ticket_text.startswith('"') and ticket_text.endswith('"'):
            ticket_text = json.loads(ticket_text)
        
        if not ticket_text or not isinstance(ticket_text, str):
            return "general"
            
        # Clean and normalize the ticket text
        text = ticket_text.strip().lower()
        
        # Define the four predefined categories
        categories = ["billing", "technical", "account", "general"]
        
        # Create a detailed classification prompt
        prompt = f"""Classify this support ticket into exactly one of these four categories:

Categories:
- billing: Issues related to payments, charges, refunds, subscriptions, invoices, pricing
- technical: Technical problems, bugs, software issues, system errors, performance problems
- account: Account access, login issues, password resets, profile changes, account settings
- general: General inquiries, questions, feedback that don't fit other categories

Ticket text: {ticket_text}

Analyze the content semantically and return ONLY the category name (billing, technical, account, or general).
Do not include any explanation or additional text."""

        # Use LLM for semantic classification
        response = llm_client.generate(prompt)
        
        # Extract and clean the response
        content = response.content.strip().lower()
        
        # Remove any markdown formatting or extra text
        if "```" in content:
            # Extract content between code blocks
            json_match = re.search(r'```(?:json|text)?\s*([^`]+)\s*```', content, re.DOTALL)
            if json_match:
                content = json_match.group(1).strip()
        
        # Clean the response to get just the category
        content = re.sub(r'[^\w\s]', '', content).strip()
        
        # Validate the response is one of our categories
        if content in categories:
            return content
        
        # Try to find category within the response
        for category in categories:
            if category in content:
                return category
                
        # Fallback: use keyword matching if LLM response is unclear
        billing_keywords = ['billing', 'charge', 'payment', 'refund', 'invoice', 'subscription', 'price', 'cost', 'fee']
        technical_keywords = ['error', 'bug', 'crash', 'problem', 'issue', 'broken', 'not working', 'technical', 'system']
        account_keywords = ['login', 'password', 'access', 'account', 'profile', 'username', 'sign in', 'reset']
        
        for keyword in billing_keywords:
            if keyword in text:
                return "billing"
                
        for keyword in technical_keywords:
            if keyword in text:
                return "technical"
                
        for keyword in account_keywords:
            if keyword in text:
                return "account"
        
        # Default to general if no clear category found
        return "general"
        
    except Exception as e:
        # Fallback to general category on any error
        return "general"