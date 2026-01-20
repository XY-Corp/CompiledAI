from typing import Any, Dict, List, Optional
import re
import json


async def normalize_address(
    address_text: str,
    # Injected context (always include)
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Parse and normalize address string into standardized components using regex patterns."""
    try:
        # Defensive input handling
        if isinstance(address_text, dict):
            # If somehow passed as dict, try to extract from a common field
            address_text = str(address_text.get('address', address_text))
        elif not isinstance(address_text, str):
            address_text = str(address_text)
        
        # Clean up the address text
        address = address_text.strip()
        
        # Initialize components with defaults
        street = ""
        city = ""
        state = ""
        zip_code = ""
        country = "USA"
        
        # Pattern 1: Full address with apartment/unit
        # "123 Main St., Apt 4B, New York, NY 10001"
        # "123 Main St, Unit 2A, Springfield, IL 62701"
        pattern1 = re.compile(r'^(.+?)(?:,\s*((?:apt|apartment|unit|suite|ste)\.?\s*\w+))?,\s*(.+?),\s*([A-Z]{2})\s+(\d{5}(?:-\d{4})?)(?:,\s*(.+?))?$', re.IGNORECASE)
        
        match = pattern1.match(address)
        if match:
            street_part = match.group(1).strip()
            apt_part = match.group(2)
            city = match.group(3).strip()
            state = match.group(4).strip().upper()
            zip_code = match.group(5).strip()
            country_part = match.group(6)
            
            # Combine street and apartment
            if apt_part:
                # Clean up apartment format - remove periods and normalize spacing
                apt_clean = re.sub(r'\.', '', apt_part.strip())
                apt_clean = re.sub(r'\s+', ' ', apt_clean)
                street = f"{street_part} {apt_clean}".strip()
            else:
                street = street_part.strip()
                
            # Remove periods from street
            street = re.sub(r'\.', '', street)
            street = re.sub(r'\s+', ' ', street)  # Normalize spaces
            
            if country_part:
                country = country_part.strip()
                
            return {
                "street": street,
                "city": city, 
                "state": state,
                "zip": zip_code,
                "country": country
            }
        
        # Pattern 2: Simple address without apartment
        # "456 Oak Ave, Boston, MA 02101"
        pattern2 = re.compile(r'^(.+?),\s*(.+?),\s*([A-Z]{2})\s+(\d{5}(?:-\d{4})?)(?:,\s*(.+?))?$', re.IGNORECASE)
        
        match = pattern2.match(address)
        if match:
            street = match.group(1).strip()
            city = match.group(2).strip()
            state = match.group(3).strip().upper()
            zip_code = match.group(4).strip()
            country_part = match.group(5)
            
            # Remove periods from street
            street = re.sub(r'\.', '', street)
            street = re.sub(r'\s+', ' ', street)  # Normalize spaces
            
            if country_part:
                country = country_part.strip()
                
            return {
                "street": street,
                "city": city,
                "state": state, 
                "zip": zip_code,
                "country": country
            }
        
        # Pattern 3: Address with state spelled out
        # "789 Pine St, Los Angeles, California 90210"
        state_abbrevs = {
            'alabama': 'AL', 'alaska': 'AK', 'arizona': 'AZ', 'arkansas': 'AR', 'california': 'CA',
            'colorado': 'CO', 'connecticut': 'CT', 'delaware': 'DE', 'florida': 'FL', 'georgia': 'GA',
            'hawaii': 'HI', 'idaho': 'ID', 'illinois': 'IL', 'indiana': 'IN', 'iowa': 'IA',
            'kansas': 'KS', 'kentucky': 'KY', 'louisiana': 'LA', 'maine': 'ME', 'maryland': 'MD',
            'massachusetts': 'MA', 'michigan': 'MI', 'minnesota': 'MN', 'mississippi': 'MS', 'missouri': 'MO',
            'montana': 'MT', 'nebraska': 'NE', 'nevada': 'NV', 'new hampshire': 'NH', 'new jersey': 'NJ',
            'new mexico': 'NM', 'new york': 'NY', 'north carolina': 'NC', 'north dakota': 'ND', 'ohio': 'OH',
            'oklahoma': 'OK', 'oregon': 'OR', 'pennsylvania': 'PA', 'rhode island': 'RI', 'south carolina': 'SC',
            'south dakota': 'SD', 'tennessee': 'TN', 'texas': 'TX', 'utah': 'UT', 'vermont': 'VT',
            'virginia': 'VA', 'washington': 'WA', 'west virginia': 'WV', 'wisconsin': 'WI', 'wyoming': 'WY'
        }
        
        # Try to find state name and zip
        for state_name, state_abbrev in state_abbrevs.items():
            pattern3 = re.compile(rf'^(.+?),\s*(.+?),\s*{re.escape(state_name)}\s+(\d{{5}}(?:-\d{{4}})?)(?:,\s*(.+?))?$', re.IGNORECASE)
            match = pattern3.match(address)
            if match:
                street = match.group(1).strip()
                city = match.group(2).strip()
                state = state_abbrev
                zip_code = match.group(3).strip()
                country_part = match.group(4)
                
                # Remove periods from street
                street = re.sub(r'\.', '', street)
                street = re.sub(r'\s+', ' ', street)  # Normalize spaces
                
                if country_part:
                    country = country_part.strip()
                    
                return {
                    "street": street,
                    "city": city,
                    "state": state,
                    "zip": zip_code,
                    "country": country
                }
        
        # If no patterns match, try to extract what we can
        # Look for zip code first
        zip_match = re.search(r'\b(\d{5}(?:-\d{4})?)\b', address)
        if zip_match:
            zip_code = zip_match.group(1)
            # Remove zip from address for further parsing
            remaining = address.replace(zip_code, '').strip().rstrip(',').strip()
            
            # Look for state (2 letters before zip)
            state_match = re.search(r'\b([A-Z]{2})\s*$', remaining, re.IGNORECASE)
            if state_match:
                state = state_match.group(1).upper()
                remaining = remaining.replace(state_match.group(0), '').strip().rstrip(',').strip()
                
                # Split remaining by commas - first part is street, last part is city
                parts = [p.strip() for p in remaining.split(',') if p.strip()]
                if len(parts) >= 2:
                    street = parts[0]
                    city = parts[-1]
                elif len(parts) == 1:
                    # Assume it's the street, city unknown
                    street = parts[0]
                    city = ""
                else:
                    street = remaining
                    
                # Clean up street
                street = re.sub(r'\.', '', street)
                street = re.sub(r'\s+', ' ', street)
                
                return {
                    "street": street,
                    "city": city,
                    "state": state,
                    "zip": zip_code,
                    "country": country
                }
        
        # Last resort - return the whole address as street
        street = re.sub(r'\.', '', address)
        street = re.sub(r'\s+', ' ', street)
        
        return {
            "street": street,
            "city": "",
            "state": "",
            "zip": "",
            "country": country
        }
        
    except Exception as e:
        # Return error structure matching the schema
        return {
            "street": f"Error parsing address: {str(e)}",
            "city": "",
            "state": "",
            "zip": "",
            "country": "USA"
        }