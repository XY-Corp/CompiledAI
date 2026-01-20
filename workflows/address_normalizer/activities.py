from typing import Any
import re
import json

async def normalize_address(
    address: str,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Parse and normalize an address string into standard components using regex patterns to identify street, city, state, ZIP, and add default country."""
    
    # Handle defensive input parsing
    if isinstance(address, dict) or isinstance(address, list):
        return {"error": "address must be a string"}
    
    try:
        # Parse JSON string if needed
        if isinstance(address, str) and address.strip().startswith('"') and address.strip().endswith('"'):
            address = json.loads(address)
    except json.JSONDecodeError:
        pass  # Not JSON, continue with original string
    
    # Clean up the address string
    address = address.strip() if isinstance(address, str) else str(address)
    
    if not address:
        return {
            "street": "",
            "city": "",
            "state": "",
            "zip": "",
            "country": "USA"
        }
    
    # Initialize components
    street = ""
    city = ""
    state = ""
    zip_code = ""
    country = "USA"
    
    # Common patterns for address parsing
    # Pattern 1: Full address with comma separators
    # Example: "123 Main St, Apt 4B, New York, NY 10001"
    full_pattern = re.compile(
        r'^(.+?),\s*(.+?),\s*([A-Z]{2})\s+(\d{5}(?:-\d{4})?)$',
        re.IGNORECASE
    )
    
    # Pattern 2: Address without apartment/unit
    # Example: "123 Main St, New York, NY 10001"
    simple_pattern = re.compile(
        r'^(.+?),\s*(.+?),\s*([A-Z]{2})\s+(\d{5}(?:-\d{4})?)$',
        re.IGNORECASE
    )
    
    # Pattern 3: Address with state and zip at the end
    # Example: "123 Main St Apt 4B New York NY 10001"
    no_comma_pattern = re.compile(
        r'^(.+?)\s+([A-Za-z\s]+?)\s+([A-Z]{2})\s+(\d{5}(?:-\d{4})?)$',
        re.IGNORECASE
    )
    
    # Pattern 4: Just street, city, state (no ZIP)
    no_zip_pattern = re.compile(
        r'^(.+?),\s*(.+?),\s*([A-Z]{2})$',
        re.IGNORECASE
    )
    
    # Try full pattern first (with commas)
    match = full_pattern.match(address)
    if match:
        street_part = match.group(1).strip()
        city = match.group(2).strip()
        state = match.group(3).upper()
        zip_code = match.group(4)
        
        # Handle apartment/unit in street
        street = street_part
    else:
        # Try no-comma pattern
        match = no_comma_pattern.match(address)
        if match:
            # Need to split street from city more carefully
            full_street_city = match.group(1).strip()
            remaining_city = match.group(2).strip()
            state = match.group(3).upper()
            zip_code = match.group(4)
            
            # Try to identify where street ends and city begins
            # Look for common street indicators
            street_indicators = r'\b(st|street|ave|avenue|rd|road|blvd|boulevard|dr|drive|ct|court|pl|place|way|ln|lane|pkwy|parkway|cir|circle|apt|apartment|unit|suite|ste)\b'
            street_match = re.search(f'(.+?{street_indicators}(?:\s+\w+)*?)(.+)', full_street_city, re.IGNORECASE)
            
            if street_match:
                street = street_match.group(1).strip()
                additional_city = street_match.group(2).strip()
                city = f"{additional_city} {remaining_city}".strip()
            else:
                # Fallback: assume last word(s) before state are city
                parts = full_street_city.split()
                if len(parts) >= 2:
                    street = " ".join(parts[:-1])
                    city = f"{parts[-1]} {remaining_city}".strip()
                else:
                    street = full_street_city
                    city = remaining_city
        else:
            # Try no-zip pattern
            match = no_zip_pattern.match(address)
            if match:
                street = match.group(1).strip()
                city = match.group(2).strip()
                state = match.group(3).upper()
                zip_code = ""
            else:
                # Try to extract ZIP code from anywhere in the string
                zip_match = re.search(r'\b(\d{5}(?:-\d{4})?)\b', address)
                if zip_match:
                    zip_code = zip_match.group(1)
                    # Remove ZIP from address for further parsing
                    address_no_zip = address.replace(zip_code, '').strip()
                else:
                    address_no_zip = address
                
                # Try to extract state (2-letter abbreviation)
                state_match = re.search(r'\b([A-Z]{2})\b', address_no_zip)
                if state_match:
                    state = state_match.group(1).upper()
                    # Remove state from address
                    address_no_state = address_no_zip.replace(state, '').strip()
                else:
                    address_no_state = address_no_zip
                
                # Split remaining into street and city (assume last part is city)
                remaining_parts = [part.strip() for part in address_no_state.split(',') if part.strip()]
                if len(remaining_parts) >= 2:
                    street = remaining_parts[0]
                    city = remaining_parts[1]
                elif len(remaining_parts) == 1:
                    # Try to split by common patterns
                    part = remaining_parts[0]
                    # Look for street indicators to separate street from city
                    street_match = re.match(r'(.+?(?:st|street|ave|avenue|rd|road|blvd|dr|ct|pl|way|ln)(?:\s+\w+)*)\s+(.+)', part, re.IGNORECASE)
                    if street_match:
                        street = street_match.group(1).strip()
                        city = street_match.group(2).strip()
                    else:
                        # Fallback: assume it's all street
                        street = part
                        city = ""
    
    # Clean up components
    street = re.sub(r'\s+', ' ', street.strip())
    city = re.sub(r'\s+', ' ', city.strip())
    state = state.strip().upper()
    zip_code = zip_code.strip()
    
    # Normalize apartment/unit formats in street
    street = re.sub(r'\s+(apt|apartment|unit|ste|suite)\s*\.?\s*', ' Apt ', street, flags=re.IGNORECASE)
    street = re.sub(r'\s+#\s*', ' Apt ', street)
    street = re.sub(r'\s+', ' ', street).strip()
    
    # Normalize street abbreviations
    street_abbrevs = {
        r'\bstreet\b': 'St',
        r'\bavenue\b': 'Ave',
        r'\broad\b': 'Rd',
        r'\bboulevard\b': 'Blvd',
        r'\bdrive\b': 'Dr',
        r'\bcourt\b': 'Ct',
        r'\bplace\b': 'Pl',
        r'\blane\b': 'Ln',
        r'\bparkway\b': 'Pkwy',
        r'\bcircle\b': 'Cir'
    }
    
    for pattern, replacement in street_abbrevs.items():
        street = re.sub(pattern, replacement, street, flags=re.IGNORECASE)
    
    return {
        "street": street,
        "city": city,
        "state": state,
        "zip": zip_code,
        "country": country
    }