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
    """Extract sender, recipient, subject, and date from email text using regex patterns."""
    
    try:
        # Handle JSON string input defensively
        if isinstance(email_text, str) and email_text.strip().startswith('{'):
            try:
                parsed_data = json.loads(email_text)
                if isinstance(parsed_data, dict) and 'email_text' in parsed_data:
                    email_text = parsed_data['email_text']
                elif isinstance(parsed_data, str):
                    email_text = parsed_data
            except json.JSONDecodeError:
                # Not JSON, treat as plain text
                pass
        
        # Initialize result with empty strings
        result = {
            "sender": "",
            "recipient": "",
            "subject": "",
            "date": ""
        }
        
        # Extract sender using regex patterns
        sender_patterns = [
            r'From:\s*(.+?)(?:\n|$)',  # From: john@example.com
            r'From:\s*"?([^"\n<]+)"?\s*<([^>\n]+)>',  # From: "John Doe" <john@example.com>
            r'From:\s*([^\n<]+)<([^>\n]+)>',  # From: John Doe <john@example.com>
            r'From:\s*([^\n]+)',  # From: anything
        ]
        
        for pattern in sender_patterns:
            sender_match = re.search(pattern, email_text, re.IGNORECASE | re.MULTILINE)
            if sender_match:
                if len(sender_match.groups()) > 1:
                    # Has both name and email, prefer email
                    result["sender"] = sender_match.group(2).strip()
                else:
                    result["sender"] = sender_match.group(1).strip()
                break
        
        # Extract recipient using regex patterns
        recipient_patterns = [
            r'To:\s*(.+?)(?:\n|$)',  # To: jane@example.com
            r'To:\s*"?([^"\n<]+)"?\s*<([^>\n]+)>',  # To: "Jane Smith" <jane@example.com>
            r'To:\s*([^\n<]+)<([^>\n]+)>',  # To: Jane Smith <jane@example.com>
            r'To:\s*([^\n]+)',  # To: anything
        ]
        
        for pattern in recipient_patterns:
            recipient_match = re.search(pattern, email_text, re.IGNORECASE | re.MULTILINE)
            if recipient_match:
                if len(recipient_match.groups()) > 1:
                    # Has both name and email, prefer email
                    result["recipient"] = recipient_match.group(2).strip()
                else:
                    result["recipient"] = recipient_match.group(1).strip()
                break
        
        # Extract subject
        subject_patterns = [
            r'Subject:\s*(.+?)(?:\n|$)',  # Subject: Meeting Tomorrow
            r'Subject:\s*([^\n]+)',  # Subject: anything
        ]
        
        for pattern in subject_patterns:
            subject_match = re.search(pattern, email_text, re.IGNORECASE | re.MULTILINE)
            if subject_match:
                result["subject"] = subject_match.group(1).strip()
                break
        
        # Extract date
        date_patterns = [
            r'Date:\s*(.+?)(?:\n|$)',  # Date: Wed, 15 Jan 2025 10:30:00 -0500
            r'Date:\s*([^\n]+)',  # Date: anything
            r'Sent:\s*(.+?)(?:\n|$)',  # Sent: (alternative date field)
            r'Sent:\s*([^\n]+)',
        ]
        
        for pattern in date_patterns:
            date_match = re.search(pattern, email_text, re.IGNORECASE | re.MULTILINE)
            if date_match:
                date_str = date_match.group(1).strip()
                # Try to extract just the date part if it's a complex timestamp
                # Look for date patterns like "2025-01-15" or "Jan 15, 2025"
                simple_date_patterns = [
                    r'(\d{4}-\d{2}-\d{2})',  # 2025-01-15
                    r'(\d{2}/\d{2}/\d{4})',  # 01/15/2025
                    r'(\d{1,2}\s+\w{3}\s+\d{4})',  # 15 Jan 2025
                    r'(\w{3}\s+\d{1,2},?\s+\d{4})',  # Jan 15, 2025
                ]
                
                date_extracted = False
                for date_pattern in simple_date_patterns:
                    simple_match = re.search(date_pattern, date_str)
                    if simple_match:
                        result["date"] = simple_match.group(1).strip()
                        date_extracted = True
                        break
                
                if not date_extracted:
                    # Use the full date string if no simple pattern matches
                    result["date"] = date_str
                break
        
        # Clean up extracted fields - remove any surrounding quotes or angle brackets
        for field in ["sender", "recipient", "subject", "date"]:
            value = result[field]
            # Remove quotes and angle brackets
            value = re.sub(r'^["\']|["\']$', '', value)
            value = re.sub(r'^<|>$', '', value)
            result[field] = value.strip()
        
        return result
        
    except Exception as e:
        # Return empty fields if parsing fails
        return {
            "sender": "",
            "recipient": "",
            "subject": "",
            "date": ""
        }