from typing import Any, Dict, List, Optional
import json

async def classify_support_ticket(
    ticket_text: str,
    categories: List[str],
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> str:
    """Classify the support ticket text into one of the predefined categories using LLM semantic analysis.
    
    Args:
        ticket_text: The complete support ticket text containing the customer's request or issue description
        categories: List of possible category classifications: billing, technical, account, general
        
    Returns:
        The single category classification result as a string
    """
    try:
        # Handle JSON string input defensively
        if isinstance(categories, str):
            categories = json.loads(categories)
            
        # Validate categories list
        if not isinstance(categories, list) or not categories:
            return "general"
            
        # Clean ticket text
        if not ticket_text or not ticket_text.strip():
            return "general"
            
        ticket_text = ticket_text.strip()
        
        # Create classification prompt
        categories_str = ", ".join(categories)
        prompt = f"""Classify this support ticket into exactly one of these categories: {categories_str}

Support ticket: {ticket_text}

Analyze the content and determine which category best fits:
- billing: Payment issues, charges, refunds, subscription problems
- technical: Software bugs, system errors, functionality problems
- account: Login issues, password resets, profile changes, account access
- general: Other inquiries, feedback, general questions

Return only the category name, nothing else."""

        # Use LLM for semantic classification
        response = llm_client.generate(prompt)
        
        # Extract and validate category from response
        result = response.content.strip().lower()
        
        # Ensure the result is one of the valid categories
        valid_categories = [cat.lower() for cat in categories]
        if result in valid_categories:
            # Return the original case version
            for cat in categories:
                if cat.lower() == result:
                    return cat
        
        # Fallback classification based on keywords if LLM result is invalid
        ticket_lower = ticket_text.lower()
        
        # Check for billing keywords
        billing_keywords = ['charge', 'bill', 'payment', 'refund', 'subscription', 'invoice', 'cost', 'price', 'money', 'credit card']
        if any(keyword in ticket_lower for keyword in billing_keywords):
            return 'billing'
            
        # Check for technical keywords  
        technical_keywords = ['error', 'bug', 'crash', 'broken', 'not working', 'problem', 'issue', 'feature', 'functionality']
        if any(keyword in ticket_lower for keyword in technical_keywords):
            return 'technical'
            
        # Check for account keywords
        account_keywords = ['login', 'password', 'account', 'profile', 'access', 'username', 'sign in', 'reset']
        if any(keyword in ticket_lower for keyword in account_keywords):
            return 'account'
            
        # Default to general
        return 'general'
        
    except Exception as e:
        # Return default category on any error
        return 'general'