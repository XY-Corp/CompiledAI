from typing import Any, Dict, List, Optional
import asyncio
import json
import re


async def parse_address_components(
    address_text: str,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extract and normalize address components from raw address text using deterministic parsing.
    
    Args:
        address_text: Complete address string containing street, apartment, city, state, and zip code information
    
    Returns:
        Dict with normalized address fields: street, city, state, zip, country
    """
    try:
        # Handle empty or null input
        if not address_text or not isinstance(address_text, str):
            return {
                "street": "",
                "city": "",
                "state": "",
                "zip": "",
                "country": "USA"
            }
        
        # Clean the input - remove extra whitespace and common punctuation
        cleaned_address = re.sub(r'\s+', ' ', address_text.strip())
        cleaned_address = cleaned_address.replace(',', ', ')  # Normalize commas
        cleaned_address = re.sub(r'\s*,\s*', ', ', cleaned_address)  # Fix comma spacing
        cleaned_address = re.sub(r'\.\s*,', ',', cleaned_address)  # Remove period before comma
        cleaned_address = cleaned_address.replace('.', '')  # Remove periods
        
        # Pattern 1: Full format with apartment - "123 Main St, Apt 4B, New York, NY 10001"
        full_pattern = r'^(.+?),\s*(.+?),\s*([A-Z]{2})\s+(\d{5}(?:-\d{4})?)$'
        match = re.match(full_pattern, cleaned_address)
        
        if match:
            street_and_apt = match.group(1).strip()
            city = match.group(2).strip()
            state = match.group(3).strip()
            zip_code = match.group(4).strip()
            
            return {
                "street": street_and_apt,
                "city": city,
                "state": state,
                "zip": zip_code,
                "country": "USA"
            }
        
        # Pattern 2: Without apartment - "123 Main St, New York, NY 10001"
        no_apt_pattern = r'^(.+?),\s*(.+?),\s*([A-Z]{2})\s+(\d{5}(?:-\d{4})?)$'
        match = re.match(no_apt_pattern, cleaned_address)
        
        if match:
            street = match.group(1).strip()
            city = match.group(2).strip()
            state = match.group(3).strip()
            zip_code = match.group(4).strip()
            
            return {
                "street": street,
                "city": city,
                "state": state,
                "zip": zip_code,
                "country": "USA"
            }
        
        # Pattern 3: Space-separated format - "123 Main St New York NY 10001"
        space_pattern = r'^(.+?)\s+([A-Za-z\s]+)\s+([A-Z]{2})\s+(\d{5}(?:-\d{4})?)$'
        match = re.match(space_pattern, cleaned_address)
        
        if match:
            street = match.group(1).strip()
            city = match.group(2).strip()
            state = match.group(3).strip()
            zip_code = match.group(4).strip()
            
            return {
                "street": street,
                "city": city,
                "state": state,
                "zip": zip_code,
                "country": "USA"
            }
        
        # Pattern 4: Try to extract zip code and work backwards
        zip_pattern = r'(\d{5}(?:-\d{4})?)$'
        zip_match = re.search(zip_pattern, cleaned_address)
        
        if zip_match:
            zip_code = zip_match.group(1)
            remaining = cleaned_address[:zip_match.start()].strip()
            
            # Look for state (2 capital letters at the end)
            state_pattern = r'\b([A-Z]{2})\s*$'
            state_match = re.search(state_pattern, remaining)
            
            if state_match:
                state = state_match.group(1)
                remaining = remaining[:state_match.start()].strip()
                
                # Split remaining into street and city
                if ', ' in remaining:
                    parts = remaining.split(', ')
                    if len(parts) >= 2:
                        street = ', '.join(parts[:-1])
                        city = parts[-1]
                    else:
                        street = parts[0] if parts else ""
                        city = ""
                else:
                    # Try to identify common street indicators
                    street_indicators = r'\b(st|street|ave|avenue|rd|road|blvd|boulevard|dr|drive|ln|lane|ct|court|pl|place|way|apt|apartment|unit|#)\b'
                    words = remaining.split()
                    
                    # Find the last street indicator
                    street_end_idx = -1
                    for i, word in enumerate(words):
                        if re.search(street_indicators, word.lower()):
                            street_end_idx = i
                    
                    if street_end_idx >= 0 and street_end_idx < len(words) - 1:
                        street = ' '.join(words[:street_end_idx + 1])
                        city = ' '.join(words[street_end_idx + 1:])
                    else:
                        # Default split - assume first part is street, rest is city
                        if len(words) >= 3:
                            street = ' '.join(words[:2])
                            city = ' '.join(words[2:])
                        else:
                            street = remaining
                            city = ""
                
                return {
                    "street": street.strip(),
                    "city": city.strip(),
                    "state": state,
                    "zip": zip_code,
                    "country": "USA"
                }
        
        # Fallback: Return the original text as street if no pattern matches
        return {
            "street": cleaned_address,
            "city": "",
            "state": "",
            "zip": "",
            "country": "USA"
        }
        
    except Exception as e:
        # Return empty structure with error indication in street field
        return {
            "street": f"Error parsing: {str(e)}",
            "city": "",
            "state": "",
            "zip": "",
            "country": "USA"
        }