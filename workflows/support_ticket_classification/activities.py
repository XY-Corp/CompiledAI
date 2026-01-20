from typing import Any, Dict, List, Optional
import asyncio
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
    """Classifies the support ticket text into one of the predefined categories using semantic analysis.
    
    Args:
        ticket_text: The complete support ticket text containing customer's issue description and any relevant details
        categories: List of valid category options for classification (billing, technical, account, general)
        
    Returns:
        str: The single category name as a string (e.g., "billing")
    """
    try:
        # Handle JSON string input defensively
        if isinstance(categories, str):
            categories = json.loads(categories)
        
        # Validate inputs
        if not ticket_text or not isinstance(ticket_text, str):
            return "general"
            
        if not categories or not isinstance(categories, list):
            categories = ["billing", "technical", "account", "general"]
        
        # Define response structure for LLM
        class TicketClassification(BaseModel):
            category: str
        
        # Create a clear classification prompt
        categories_text = ", ".join(categories)
        prompt = f"""Classify this support ticket into exactly one of these categories: {categories_text}

Support Ticket:
{ticket_text}

Instructions:
- Read the ticket content carefully
- Choose the single most appropriate category from: {categories_text}
- Consider keywords and context:
  * billing: payments, invoices, charges, refunds, pricing
  * technical: bugs, errors, not working, crashes, performance
  * account: login, password, profile, settings, access
  * general: questions, information requests, other issues
- Return ONLY the category name

Return the category as JSON: {{"category": "category_name"}}"""
        
        # Use LLM client for semantic classification
        response = llm_client.generate(prompt)
        content = response.content.strip()
        
        # Extract JSON from response (handle markdown code blocks)
        if "```" in content:
            import re
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
            validated = TicketClassification(**data)
            category = validated.category.lower()
            
            # Ensure category is in allowed list
            if category in [c.lower() for c in categories]:
                return category
            else:
                # Fallback to most similar category
                for cat in categories:
                    if cat.lower() in content.lower():
                        return cat.lower()
                return "general"
                
        except (json.JSONDecodeError, ValueError):
            # Fallback: simple keyword matching
            ticket_lower = ticket_text.lower()
            
            # Check for billing keywords
            billing_keywords = ["bill", "payment", "charge", "invoice", "refund", "price", "cost", "fee"]
            if any(keyword in ticket_lower for keyword in billing_keywords):
                return "billing"
            
            # Check for technical keywords
            tech_keywords = ["error", "bug", "crash", "not working", "broken", "issue", "problem", "performance"]
            if any(keyword in ticket_lower for keyword in tech_keywords):
                return "technical"
            
            # Check for account keywords
            account_keywords = ["login", "password", "account", "profile", "access", "settings", "username"]
            if any(keyword in ticket_lower for keyword in account_keywords):
                return "account"
            
            # Default to general
            return "general"
            
    except Exception as e:
        # Fallback to general category on any error
        return "general"