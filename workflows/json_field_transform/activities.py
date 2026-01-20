from typing import Any, Dict, List, Optional
import json


async def transform_json_structure(
    source_data: dict,
    schema_definition: dict,
    # Injected context (always include)
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Transform JSON data from source format to target format by mapping and combining fields."""
    try:
        # Defensive parsing - handle JSON strings if needed
        if isinstance(source_data, str):
            source_data = json.loads(source_data)
        if isinstance(schema_definition, str):
            schema_definition = json.loads(schema_definition)

        # Validate types
        if not isinstance(source_data, dict):
            return {"error": f"source_data must be dict, got {type(source_data).__name__}"}
        if not isinstance(schema_definition, dict):
            return {"error": f"schema_definition must be dict, got {type(schema_definition).__name__}"}

        # Transform the JSON structure based on the specific mapping
        # According to the schema, we need to:
        # - Combine first_name and last_name into fullName
        # - Map email_address to email
        
        transformed = {}
        
        # Handle fullName transformation
        if "fullName" in schema_definition:
            first_name = source_data.get("first_name", "")
            last_name = source_data.get("last_name", "")
            transformed["fullName"] = f"{first_name} {last_name}".strip()
        
        # Handle email mapping
        if "email" in schema_definition:
            transformed["email"] = source_data.get("email_address", "")
        
        # Handle any other direct field mappings that might be in the schema
        for target_field in schema_definition:
            if target_field not in transformed:
                # Check if there's a direct mapping from source
                if target_field in source_data:
                    transformed[target_field] = source_data[target_field]

        return transformed
        
    except json.JSONDecodeError as e:
        return {"error": f"Invalid JSON: {e}"}
    except KeyError as e:
        return {"error": f"Missing field: {e}"}
    except Exception as e:
        return {"error": f"Transformation failed: {e}"}