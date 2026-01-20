from typing import Any, Dict, List, Optional
import re
import json

async def parse_address_components(
    address_text: str,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Parses and normalizes a raw address string into structured components using regex patterns and string manipulation.
    
    Args:
        address_text: The complete address string containing street, apartment, city, state, and zip code information
        
    Returns:
        Dict with normalized address structure containing street, city, state, zip, and country fields
    """
    if not address_text or not isinstance(address_text, str):
        return {
            "street": "",
            "city": "",
            "state": "",
            "zip": "",
            "country": "USA"
        }
    
    # Clean up the address text
    cleaned = address_text.strip()
    
    # Remove periods after common abbreviations
    cleaned = re.sub(r'\bSt\.\s*', 'St ', cleaned)
    cleaned = re.sub(r'\bAve\.\s*', 'Ave ', cleaned)
    cleaned = re.sub(r'\bBlvd\.\s*', 'Blvd ', cleaned)
    cleaned = re.sub(r'\bDr\.\s*', 'Dr ', cleaned)
    cleaned = re.sub(r'\bRd\.\s*', 'Rd ', cleaned)
    
    # Try different patterns based on common address formats
    patterns = [
        # Pattern 1: "123 Main St, Apt 4B, New York, NY 10001"
        r'^(.+?),\s*(.+?),\s*(.+?),\s*([A-Z]{2})\s+(\d{5}(?:-\d{4})?)$',
        # Pattern 2: "123 Main St Apt 4B, New York, NY 10001"
        r'^(.+?),\s*(.+?),\s*([A-Z]{2})\s+(\d{5}(?:-\d{4})?)$',
        # Pattern 3: "123 Main St, New York NY 10001"
        r'^(.+?),\s*(.+?)\s+([A-Z]{2})\s+(\d{5}(?:-\d{4})?)$',
        # Pattern 4: "123 Main St New York NY 10001" (no commas)
        r'^(.+?)\s+(.+?)\s+([A-Z]{2})\s+(\d{5}(?:-\d{4})?)$'
    ]
    
    street = ""
    city = ""
    state = ""
    zip_code = ""
    
    for i, pattern in enumerate(patterns):
        match = re.match(pattern, cleaned)
        if match:
            if i == 0:  # Pattern with apartment/unit
                street_part = match.group(1).strip()
                apt_part = match.group(2).strip()
                street = f"{street_part} {apt_part}".strip()
                city = match.group(3).strip()
                state = match.group(4).strip()
                zip_code = match.group(5).strip()
            elif i == 1:  # Pattern without separate apartment
                street = match.group(1).strip()
                city = match.group(2).strip()
                state = match.group(3).strip()
                zip_code = match.group(4).strip()
            elif i == 2:  # Pattern with comma before city
                street = match.group(1).strip()
                city = match.group(2).strip()
                state = match.group(3).strip()
                zip_code = match.group(4).strip()
            elif i == 3:  # Pattern without commas
                # Need to split street from city more carefully
                parts = match.group(1).split()
                # Assume last 2-3 words before state are city
                if len(parts) >= 3:
                    street = " ".join(parts[:-2])
                    city = " ".join(parts[-2:])
                else:
                    street = match.group(1).strip()
                    city = match.group(2).strip()
                state = match.group(3).strip()
                zip_code = match.group(4).strip()
            break
    
    # If no pattern matched, try to extract what we can
    if not street and not city and not state and not zip_code:
        # Look for zip code first
        zip_match = re.search(r'\b(\d{5}(?:-\d{4})?)\b', cleaned)
        if zip_match:
            zip_code = zip_match.group(1)
            # Remove zip from string
            remaining = cleaned.replace(zip_code, "").strip()
        else:
            remaining = cleaned
        
        # Look for state (2 capital letters)
        state_match = re.search(r'\b([A-Z]{2})\b', remaining)
        if state_match:
            state = state_match.group(1)
            # Remove state from string
            remaining = remaining.replace(state, "").strip()
        
        # What's left is likely street and city
        # Split on comma if present
        if "," in remaining:
            parts = remaining.split(",")
            if len(parts) >= 2:
                street = parts[0].strip()
                city = parts[1].strip()
            else:
                street = remaining.strip()
        else:
            # No comma - assume everything is street address
            street = remaining.strip()
    
    # Clean up extracted components
    street = re.sub(r'\s+', ' ', street).strip()
    city = re.sub(r'\s+', ' ', city).strip()
    state = state.strip().upper() if state else ""
    zip_code = zip_code.strip()
    
    # Remove trailing commas or periods
    street = street.rstrip('.,')
    city = city.rstrip('.,')
    
    return {
        "street": street,
        "city": city,
        "state": state,
        "zip": zip_code,
        "country": "USA"
    }