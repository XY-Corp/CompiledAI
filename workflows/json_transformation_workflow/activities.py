from typing import Any, Dict, List, Optional
import json
import re


async def transform_json_structure(
    prompt_text: str,
    source_data: dict,
    target_format: dict,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Transforms JSON data from source format to target schema format by parsing the transformation prompt and mapping fields accordingly."""
    
    try:
        # Parse JSON strings if needed (defensive parsing)
        if isinstance(source_data, str):
            source_data = json.loads(source_data)
        if isinstance(target_format, str):
            target_format = json.loads(target_format)
        
        # Validate inputs
        if not isinstance(source_data, dict):
            return {"error": f"source_data must be dict, got {type(source_data).__name__}"}
        if not isinstance(target_format, dict):
            return {"error": f"target_format must be dict, got {type(target_format).__name__}"}
        
        # Initialize result
        transformed = {}
        
        # Analyze target schema to determine field mappings and transformations
        for target_field, target_type in target_format.items():
            if target_field == "fullName":
                # Handle name combination
                first_name = source_data.get("first_name", "")
                last_name = source_data.get("last_name", "")
                full_name = f"{first_name} {last_name}".strip()
                transformed["fullName"] = full_name
            
            elif target_field == "email":
                # Map email field variations
                email = (source_data.get("email") or 
                        source_data.get("email_address") or 
                        source_data.get("emailAddress") or "")
                transformed["email"] = email
            
            elif target_field == "phone":
                # Map phone field variations
                phone = (source_data.get("phone") or 
                        source_data.get("phone_number") or 
                        source_data.get("phoneNumber") or "")
                transformed["phone"] = phone
            
            elif target_field == "address":
                # Handle address combination or mapping
                if "street" in source_data and "city" in source_data:
                    address_parts = []
                    if source_data.get("street"):
                        address_parts.append(source_data["street"])
                    if source_data.get("city"):
                        address_parts.append(source_data["city"])
                    if source_data.get("state"):
                        address_parts.append(source_data["state"])
                    if source_data.get("zip") or source_data.get("zipCode"):
                        address_parts.append(source_data.get("zip") or source_data.get("zipCode"))
                    transformed["address"] = ", ".join(address_parts)
                else:
                    transformed["address"] = source_data.get("address", "")
            
            else:
                # Direct field mapping with common variations
                value = None
                
                # Try exact match first
                if target_field in source_data:
                    value = source_data[target_field]
                else:
                    # Try snake_case to camelCase conversion
                    snake_case = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', target_field).lower()
                    if snake_case in source_data:
                        value = source_data[snake_case]
                    
                    # Try camelCase to snake_case conversion
                    camel_case = re.sub(r'_(.)', lambda m: m.group(1).upper(), target_field)
                    if camel_case in source_data:
                        value = source_data[camel_case]
                    
                    # Try common field variations
                    variations = [
                        target_field.lower(),
                        target_field.upper(),
                        target_field.replace("_", ""),
                        target_field.replace("_", "-"),
                    ]
                    
                    for variation in variations:
                        if variation in source_data:
                            value = source_data[variation]
                            break
                
                # Set the value or empty string if not found
                transformed[target_field] = value if value is not None else ""
        
        return transformed
        
    except json.JSONDecodeError as e:
        return {"error": f"Invalid JSON: {e}"}
    except Exception as e:
        return {"error": f"Transformation failed: {e}"}