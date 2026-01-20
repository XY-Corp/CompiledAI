from typing import Any, Dict, List, Optional
import asyncio
import json
import re

async def extract_email_headers(
    email_content: str,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extract sender, recipient, subject, and date from email text using regex patterns for standard email headers."""
    
    # Defensive input handling - parse JSON string if needed
    try:
        if isinstance(email_content, str) and email_content.startswith('{'):
            email_content = json.loads(email_content)
            if isinstance(email_content, dict):
                # If it's a dict, we might need to extract the actual email content
                email_content = email_content.get('email_text', email_content.get('content', str(email_content)))
    except json.JSONDecodeError:
        pass  # Continue with the original string
    
    # Ensure we have a string to work with
    if not isinstance(email_content, str):
        email_content = str(email_content)
    
    # Initialize result with empty strings (following the exact output schema)
    result = {
        "sender": "",
        "recipient": "",
        "subject": "",
        "date": ""
    }
    
    # Extract sender (From field)
    sender_patterns = [
        r'^From:\s*(.+?)(?:\n|$)',  # Standard "From:" header
        r'^from:\s*(.+?)(?:\n|$)',  # Lowercase variation
        r'\nFrom:\s*(.+?)(?:\n|$)',  # Mid-text From header
        r'\nfrom:\s*(.+?)(?:\n|$)',  # Mid-text lowercase
    ]
    
    for pattern in sender_patterns:
        sender_match = re.search(pattern, email_content, re.MULTILINE | re.IGNORECASE)
        if sender_match:
            result["sender"] = sender_match.group(1).strip()
            break
    
    # Extract recipient (To field)
    recipient_patterns = [
        r'^To:\s*(.+?)(?:\n|$)',  # Standard "To:" header
        r'^to:\s*(.+?)(?:\n|$)',  # Lowercase variation
        r'\nTo:\s*(.+?)(?:\n|$)',  # Mid-text To header
        r'\nto:\s*(.+?)(?:\n|$)',  # Mid-text lowercase
    ]
    
    for pattern in recipient_patterns:
        recipient_match = re.search(pattern, email_content, re.MULTILINE | re.IGNORECASE)
        if recipient_match:
            result["recipient"] = recipient_match.group(1).strip()
            break
    
    # Extract subject (Subject field)
    subject_patterns = [
        r'^Subject:\s*(.+?)(?:\n|$)',  # Standard "Subject:" header
        r'^subject:\s*(.+?)(?:\n|$)',  # Lowercase variation
        r'\nSubject:\s*(.+?)(?:\n|$)',  # Mid-text Subject header
        r'\nsubject:\s*(.+?)(?:\n|$)',  # Mid-text lowercase
    ]
    
    for pattern in subject_patterns:
        subject_match = re.search(pattern, email_content, re.MULTILINE | re.IGNORECASE)
        if subject_match:
            result["subject"] = subject_match.group(1).strip()
            break
    
    # Extract date (Date field)
    date_patterns = [
        r'^Date:\s*(.+?)(?:\n|$)',  # Standard "Date:" header
        r'^date:\s*(.+?)(?:\n|$)',  # Lowercase variation
        r'\nDate:\s*(.+?)(?:\n|$)',  # Mid-text Date header
        r'\ndate:\s*(.+?)(?:\n|$)',  # Mid-text lowercase
    ]
    
    for pattern in date_patterns:
        date_match = re.search(pattern, email_content, re.MULTILINE | re.IGNORECASE)
        if date_match:
            result["date"] = date_match.group(1).strip()
            break
    
    return result