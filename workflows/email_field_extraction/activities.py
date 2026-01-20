from typing import Any, Dict, List, Optional
import re


async def extract_email_fields(
    email_text: str,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extract sender, recipient, subject, and date fields from email text using regex pattern matching.
    
    Args:
        email_text: The complete email text containing headers (From, To, Subject, Date) and body content to parse
        
    Returns:
        Dict containing extracted email fields: sender, recipient, subject, date
    """
    # Initialize default values
    result = {
        "sender": "",
        "recipient": "", 
        "subject": "",
        "date": ""
    }
    
    # Extract sender using regex for "From:" header
    sender_match = re.search(r'^From:\s*(.+?)(?:\n|$)', email_text, re.IGNORECASE | re.MULTILINE)
    if sender_match:
        result["sender"] = sender_match.group(1).strip()
    
    # Extract recipient using regex for "To:" header
    recipient_match = re.search(r'^To:\s*(.+?)(?:\n|$)', email_text, re.IGNORECASE | re.MULTILINE)
    if recipient_match:
        result["recipient"] = recipient_match.group(1).strip()
    
    # Extract subject using regex for "Subject:" header
    subject_match = re.search(r'^Subject:\s*(.+?)(?:\n|$)', email_text, re.IGNORECASE | re.MULTILINE)
    if subject_match:
        result["subject"] = subject_match.group(1).strip()
    
    # Extract date using regex for "Date:" header
    date_match = re.search(r'^Date:\s*(.+?)(?:\n|$)', email_text, re.IGNORECASE | re.MULTILINE)
    if date_match:
        result["date"] = date_match.group(1).strip()
    
    return result