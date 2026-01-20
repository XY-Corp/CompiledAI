from typing import Any, Dict, List, Optional
import json


async def transform_json_fields(
    source_data: dict,
    target_format: dict,
    # Injected context (always include)
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Transform JSON structure by mapping source fields to target format, combining first_name and last_name into fullName and mapping email_address to email."""
    try:
        # Handle defensive input parsing for both parameters
        if isinstance(source_data, str):
            source_data = json.loads(source_data)
        if isinstance(target_format, str):
            target_format = json.loads(target_format)
        
        # Validate types
        if not isinstance(source_data, dict):
            return {"error": f"source_data must be dict, got {type(source_data).__name__}"}
        if not isinstance(target_format, dict):
            return {"error": f"target_format must be dict, got {type(target_format).__name__}"}
        
        # Transform the data according to business logic
        transformed = {}
        
        # Combine first_name and last_name into fullName
        if "fullName" in target_format:
            first_name = source_data.get("first_name", "")
            last_name = source_data.get("last_name", "")
            transformed["fullName"] = f"{first_name} {last_name}".strip()
        
        # Map email_address to email
        if "email" in target_format:
            transformed["email"] = source_data.get("email_address", "")
        
        return transformed
        
    except json.JSONDecodeError as e:
        return {"error": f"Invalid JSON: {e}"}
    except Exception as e:
        return {"error": f"Transformation error: {e}"}