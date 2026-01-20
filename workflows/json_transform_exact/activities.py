from typing import Any, Dict, List, Optional
import json


async def transform_json_schema(
    source_data: dict,
    target_format: dict,
    # Injected context (always include)
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Transforms source JSON data to target schema format with field mapping and value calculations (id=product_id, name=product_name, total=price_usd*qty)."""
    try:
        # Parse JSON strings if needed (defensive input handling)
        if isinstance(source_data, str):
            source_data = json.loads(source_data)
        if isinstance(target_format, str):
            target_format = json.loads(target_format)
            
        # Validate types
        if not isinstance(source_data, dict):
            return {"error": f"source_data must be dict, got {type(source_data).__name__}"}
        if not isinstance(target_format, dict):
            return {"error": f"target_format must be dict, got {type(target_format).__name__}"}
        
        # Transform the data according to the specific mapping requirements
        transformed = {}
        
        # Apply the exact transformation logic as specified:
        # id field maps from product_id
        if "id" in target_format and "product_id" in source_data:
            transformed["id"] = str(source_data["product_id"])
            
        # name field maps from product_name
        if "name" in target_format and "product_name" in source_data:
            transformed["name"] = str(source_data["product_name"])
            
        # total field is calculated as price_usd multiplied by qty
        if "total" in target_format and "price_usd" in source_data and "qty" in source_data:
            price = float(source_data["price_usd"])
            quantity = int(source_data["qty"])
            transformed["total"] = price * quantity
            
        return transformed
        
    except json.JSONDecodeError as e:
        return {"error": f"Invalid JSON: {e}"}
    except (ValueError, TypeError, KeyError) as e:
        return {"error": f"Data transformation error: {e}"}
    except Exception as e:
        return {"error": f"Unexpected error: {e}"}