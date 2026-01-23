from typing import Any, Dict, List, Optional
import asyncio
import json
import re


async def extract_email_fields(
    email_text: str,
    # Injected context (always include)
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extracts sender, recipient, subject, and date fields from email text using regex patterns to parse email headers."""
    
    try:
        # Handle defensive input - email_text might be None
        if email_text is None:
            return {
                "sender": "",
                "recipient": "",
                "subject": "",
                "date": ""
            }
        
        # Parse JSON string if needed
        if isinstance(email_text, dict):
            # If it's already a dict, it might contain the email text in a field
            email_text = str(email_text)
        
        # Extract sender (From: header)
        sender_match = re.search(r'From:\s*([^\n\r]+)', email_text, re.IGNORECASE)
        sender = sender_match.group(1).strip() if sender_match else ""
        
        # Extract recipient (To: header)
        recipient_match = re.search(r'To:\s*([^\n\r]+)', email_text, re.IGNORECASE)
        recipient = recipient_match.group(1).strip() if recipient_match else ""
        
        # Extract subject (Subject: header)
        subject_match = re.search(r'Subject:\s*([^\n\r]+)', email_text, re.IGNORECASE)
        subject = subject_match.group(1).strip() if subject_match else ""
        
        # Extract date (Date: header)
        date_match = re.search(r'Date:\s*([^\n\r]+)', email_text, re.IGNORECASE)
        date = date_match.group(1).strip() if date_match else ""
        
        # Clean up email addresses by removing angle brackets and display names
        # Example: "John Doe <john.doe@example.com>" -> "john.doe@example.com"
        def clean_email(email_str: str) -> str:
            if not email_str:
                return ""
            # Extract email from angle brackets if present
            angle_match = re.search(r'<([^>]+)>', email_str)
            if angle_match:
                return angle_match.group(1).strip()
            # If no angle brackets, look for email pattern
            email_pattern = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', email_str)
            if email_pattern:
                return email_pattern.group(0).strip()
            # Return as-is if no email pattern found
            return email_str.strip()
        
        # Clean the email addresses
        sender = clean_email(sender)
        recipient = clean_email(recipient)
        
        return {
            "sender": sender,
            "recipient": recipient,
            "subject": subject,
            "date": date
        }
        
    except Exception as e:
        # Return empty fields if parsing fails
        return {
            "sender": "",
            "recipient": "",
            "subject": "",
            "date": ""
        }