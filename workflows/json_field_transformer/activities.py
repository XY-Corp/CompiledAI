from typing import Any, Dict, List, Optional
import json
import re

async def transform_json_fields(
    source_data: dict,
    schema_definition: dict,
    # Injected context (always include)
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Transform source JSON to target format by mapping and combining fields according to target schema requirements."""
    
    try:
        # Defensive input handling - parse JSON strings if needed
        if isinstance(source_data, str):
            source_data = json.loads(source_data)
        if isinstance(schema_definition, str):
            schema_definition = json.loads(schema_definition)

        # Validate types
        if not isinstance(source_data, dict):
            return {"error": f"source_data must be dict, got {type(source_data).__name__}"}
        if not isinstance(schema_definition, dict):
            return {"error": f"schema_definition must be dict, got {type(schema_definition).__name__}"}

        # Transform data according to target schema
        result = {}
        
        for target_field, target_type in schema_definition.items():
            if target_field == "fullName":
                # Combine first_name and last_name fields
                first_name = source_data.get("first_name", "")
                last_name = source_data.get("last_name", "")
                result["fullName"] = f"{first_name} {last_name}".strip()
            
            elif target_field == "email":
                # Map email_address to email, or use email if it exists
                result["email"] = source_data.get("email_address") or source_data.get("email", "")
            
            else:
                # Try to find exact match first
                if target_field in source_data:
                    result[target_field] = source_data[target_field]
                else:
                    # Try common field mapping patterns
                    field_mappings = {
                        "name": ["full_name", "fullname", "display_name"],
                        "phone": ["phone_number", "phoneNumber", "mobile"],
                        "address": ["street_address", "addr", "location"],
                        "city": ["city_name", "locality"],
                        "state": ["state_code", "province", "region"],
                        "zip": ["zip_code", "zipcode", "postal_code", "postcode"],
                        "country": ["country_code", "nation"],
                        "company": ["company_name", "organization", "employer"],
                        "title": ["job_title", "position", "role"],
                        "description": ["desc", "details", "summary"],
                        "date": ["created_date", "timestamp", "created_at"],
                        "id": ["identifier", "uid", "user_id"],
                        "url": ["website", "link", "homepage"]
                    }
                    
                    # Try to find a mapping
                    mapped_value = None
                    if target_field.lower() in field_mappings:
                        for potential_source in field_mappings[target_field.lower()]:
                            if potential_source in source_data:
                                mapped_value = source_data[potential_source]
                                break
                    
                    # Try partial matches (case-insensitive)
                    if mapped_value is None:
                        target_lower = target_field.lower()
                        for source_key, source_value in source_data.items():
                            source_lower = source_key.lower()
                            if (target_lower in source_lower or 
                                source_lower in target_lower or 
                                target_lower.replace("_", "") == source_lower.replace("_", "")):
                                mapped_value = source_value
                                break
                    
                    result[target_field] = mapped_value if mapped_value is not None else ""

        return result

    except json.JSONDecodeError as e:
        return {"error": f"Invalid JSON: {e}"}
    except Exception as e:
        return {"error": f"Transformation error: {e}"}