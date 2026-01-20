from typing import Any, Dict, List, Optional
import re
import json


async def normalize_address_format(
    address: str,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Parse and normalize a street address string into structured components using regex patterns and string manipulation."""
    try:
        # Handle JSON string input defensively
        if isinstance(address, str) and address.startswith('{'):
            try:
                address = json.loads(address)
                if isinstance(address, dict) and 'address' in address:
                    address = address['address']
            except json.JSONDecodeError:
                pass  # Not JSON, use as string
        
        if not isinstance(address, str):
            return {"street": "", "city": "", "state": "", "zip": "", "country": "USA"}
        
        address = address.strip()
        if not address:
            return {"street": "", "city": "", "state": "", "zip": "", "country": "USA"}
        
        # Split by commas and clean up each part
        parts = [part.strip() for part in address.split(',')]
        
        # Initialize components
        street = ""
        city = ""
        state = ""
        zip_code = ""
        country = "USA"
        
        if len(parts) >= 3:
            # Standard format: "123 Main St., Apt 4B, New York, NY 10001"
            # or "123 Main St, New York, NY 10001"
            
            # Last part should contain state and zip
            last_part = parts[-1].strip()
            state_zip_match = re.search(r'([A-Z]{2})\s*(\d{5}(?:-\d{4})?)', last_part)
            
            if state_zip_match:
                state = state_zip_match.group(1)
                zip_code = state_zip_match.group(2).split('-')[0]  # Remove extended zip
                
                # City is the second to last part
                city = parts[-2].strip()
                
                # Street is everything before city (combine first parts)
                street_parts = parts[:-2]
                street = ', '.join(street_parts).strip()
                
                # Clean up street - remove extra punctuation and normalize
                street = re.sub(r'[,\.]+$', '', street)  # Remove trailing commas/periods
                street = re.sub(r'\s+', ' ', street)  # Normalize spaces
                street = street.replace('.,', '').replace(',.', '')  # Clean up punctuation
                
        elif len(parts) == 2:
            # Format: "123 Main St, New York NY 10001"
            street = parts[0].strip()
            location_part = parts[1].strip()
            
            # Try to extract city, state, zip from second part
            state_zip_match = re.search(r'(.+?)\s+([A-Z]{2})\s*(\d{5}(?:-\d{4})?)', location_part)
            if state_zip_match:
                city = state_zip_match.group(1).strip()
                state = state_zip_match.group(2)
                zip_code = state_zip_match.group(3).split('-')[0]
            else:
                city = location_part
                
        elif len(parts) == 1:
            # Single string - try to parse everything
            single_part = parts[0].strip()
            
            # Look for state and zip at the end
            state_zip_match = re.search(r'(.+?)\s+([A-Z]{2})\s*(\d{5}(?:-\d{4})?)$', single_part)
            if state_zip_match:
                before_state = state_zip_match.group(1).strip()
                state = state_zip_match.group(2)
                zip_code = state_zip_match.group(3).split('-')[0]
                
                # Try to separate street and city from what's before state
                # Look for common city patterns
                city_match = re.search(r'(.+?)\s+((?:[A-Z][a-z]+\s*)+)$', before_state)
                if city_match:
                    street = city_match.group(1).strip()
                    city = city_match.group(2).strip()
                else:
                    # Fallback: assume last word(s) are city
                    words = before_state.split()
                    if len(words) > 1:
                        street = ' '.join(words[:-1])
                        city = words[-1]
                    else:
                        street = before_state
            else:
                street = single_part
        
        # Final cleanup
        street = re.sub(r'[,\.]+$', '', street.strip())  # Remove trailing punctuation
        street = re.sub(r'\s+', ' ', street)  # Normalize whitespace
        city = city.strip()
        state = state.strip().upper()
        zip_code = zip_code.strip()
        
        # Handle apartment/unit normalization in street
        street = re.sub(r'\s*,\s*', ' ', street)  # Replace commas with spaces
        street = re.sub(r'\.+', '', street)  # Remove periods
        street = re.sub(r'\s+', ' ', street).strip()  # Normalize spaces
        
        return {
            "street": street,
            "city": city,
            "state": state,
            "zip": zip_code,
            "country": country
        }
        
    except Exception as e:
        # Return empty structure on error
        return {
            "street": "",
            "city": "",
            "state": "",
            "zip": "",
            "country": "USA"
        }