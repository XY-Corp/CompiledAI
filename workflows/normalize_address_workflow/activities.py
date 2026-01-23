from typing import Any, Dict, List, Optional
import re
import json

async def normalize_address_data(
    address_text: str,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Parse and normalize raw address text into standardized format with street, city, state, zip, and country fields using deterministic regex patterns."""
    
    # Handle defensive input parsing
    if isinstance(address_text, dict) or isinstance(address_text, list):
        return {"error": f"address_text must be string, got {type(address_text).__name__}"}
    
    if not address_text or not isinstance(address_text, str):
        return {"error": "address_text is required and must be a non-empty string"}
    
    # Clean up the input text
    address_text = address_text.strip()
    
    # Initialize default values
    street = ""
    city = ""
    state = ""
    zip_code = ""
    country = "USA"  # Default country
    
    try:
        # Pattern 1: Full address with comma separators
        # Example: "123 Main St., Apt 4B, New York, NY 10001"
        # Pattern: street_info, city, state zip
        pattern1 = r'^(.+?),\s*([^,]+),\s*([A-Z]{2})\s+(\d{5}(?:-\d{4})?)(?:\s*,\s*([^,]+))?$'
        match1 = re.match(pattern1, address_text, re.IGNORECASE)
        
        if match1:
            street = match1.group(1).strip()
            city = match1.group(2).strip()
            state = match1.group(3).upper()
            zip_code = match1.group(4)
            if match1.group(5):
                country = match1.group(5).strip()
        else:
            # Pattern 2: Address without commas
            # Example: "123 Main Street Apt 4B New York NY 10001"
            # Look for state and zip at the end
            pattern2 = r'^(.+?)\s+([A-Z]{2})\s+(\d{5}(?:-\d{4})?)(?:\s+(.+))?$'
            match2 = re.search(pattern2, address_text, re.IGNORECASE)
            
            if match2:
                street_and_city = match2.group(1).strip()
                state = match2.group(2).upper()
                zip_code = match2.group(3)
                if match2.group(4):
                    country = match2.group(4).strip()
                
                # Try to separate street from city in the remaining text
                # Look for common city patterns or split on last space
                words = street_and_city.split()
                if len(words) >= 2:
                    # Assume last 1-2 words are city, rest is street
                    if len(words) >= 3:
                        street = ' '.join(words[:-2])
                        city = ' '.join(words[-2:])
                    else:
                        street = words[0]
                        city = words[1]
                else:
                    street = street_and_city
                    city = ""
            else:
                # Pattern 3: Just try to extract zip and state if present
                zip_match = re.search(r'\b(\d{5}(?:-\d{4})?)\b', address_text)
                state_match = re.search(r'\b([A-Z]{2})\b', address_text)
                
                if zip_match:
                    zip_code = zip_match.group(1)
                if state_match:
                    state = state_match.group(1)
                
                # Remove zip and state from address, what's left is street and city
                remaining = address_text
                if zip_match:
                    remaining = remaining.replace(zip_match.group(0), '').strip()
                if state_match:
                    remaining = remaining.replace(state_match.group(0), '').strip()
                
                # Clean up extra spaces and commas
                remaining = re.sub(r'\s*,\s*', ' ', remaining).strip()
                remaining = re.sub(r'\s+', ' ', remaining)
                
                # Try to split into street and city
                words = remaining.split()
                if len(words) >= 2:
                    # Assume last 1-2 words are city
                    if len(words) >= 3:
                        street = ' '.join(words[:-2])
                        city = ' '.join(words[-2:])
                    else:
                        street = words[0]
                        city = words[1]
                else:
                    street = remaining
        
        # Clean up punctuation and normalize formatting
        street = re.sub(r'[,.]', '', street).strip()
        street = re.sub(r'\s+', ' ', street)  # Normalize multiple spaces
        
        city = re.sub(r'[,.]', '', city).strip()
        city = re.sub(r'\s+', ' ', city)
        
        # Capitalize city name properly
        if city:
            city = ' '.join(word.capitalize() for word in city.split())
        
        # Normalize street abbreviations
        street = street.replace('St.', 'St').replace('Ave.', 'Ave').replace('Rd.', 'Rd').replace('Dr.', 'Dr')
        
        return {
            "street": street,
            "city": city,
            "state": state,
            "zip": zip_code,
            "country": country
        }
        
    except Exception as e:
        return {"error": f"Failed to parse address: {str(e)}"}