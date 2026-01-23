from typing import Any, Dict, List, Optional
import re
import json


async def extract_email_fields(
    email_text: str,
    # Injected context (always include)
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extract structured email fields (sender, recipient, subject, date) from raw email text using regex pattern matching."""
    
    # Handle defensive input parsing for string inputs
    if isinstance(email_text, str):
        # email_text is already a string, no parsing needed
        pass
    else:
        return {"error": f"email_text must be string, got {type(email_text).__name__}"}
    
    # Initialize result dictionary
    result = {
        "sender": "",
        "recipient": "",
        "subject": "",
        "date": ""
    }
    
    try:
        # Extract sender from "From:" header
        from_match = re.search(r'From:\s*(.+?)(?:\n|$)', email_text, re.IGNORECASE)
        if from_match:
            result["sender"] = from_match.group(1).strip()
        
        # Extract recipient from "To:" header
        to_match = re.search(r'To:\s*(.+?)(?:\n|$)', email_text, re.IGNORECASE)
        if to_match:
            result["recipient"] = to_match.group(1).strip()
        
        # Extract subject from "Subject:" header
        subject_match = re.search(r'Subject:\s*(.+?)(?:\n|$)', email_text, re.IGNORECASE)
        if subject_match:
            result["subject"] = subject_match.group(1).strip()
        
        # Extract date from "Date:" header
        date_match = re.search(r'Date:\s*(.+?)(?:\n|$)', email_text, re.IGNORECASE)
        if date_match:
            result["date"] = date_match.group(1).strip()
        
        return result
        
    except Exception as e:
        # Return empty fields if extraction fails
        return {
            "sender": "",
            "recipient": "",
            "subject": "",
            "date": ""
        }