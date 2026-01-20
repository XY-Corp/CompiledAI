from typing import Any, Dict, List, Optional
import json


async def transform_json_structure(
    source_json: dict,
    target_schema: dict,
    # Injected context (always include)
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Transform source JSON to target format by mapping product_id to id, product_name to name, and calculating total as price_usd * qty."""
    
    try:
        # Handle JSON string inputs defensively
        if isinstance(source_json, str):
            source_json = json.loads(source_json)
        if isinstance(target_schema, str):
            target_schema = json.loads(target_schema)
            
        # Validate types
        if not isinstance(source_json, dict):
            return {"error": f"source_json must be dict, got {type(source_json).__name__}"}
        if not isinstance(target_schema, dict):
            return {"error": f"target_schema must be dict, got {type(target_schema).__name__}"}
        
        # Extract required fields from source
        product_id = source_json.get('product_id', '')
        product_name = source_json.get('product_name', '')
        price_usd = source_json.get('price_usd', 0)
        qty = source_json.get('qty', 0)
        
        # Convert to appropriate types
        try:
            price_usd = float(price_usd)
            qty = int(qty)
        except (ValueError, TypeError):
            price_usd = 0.0
            qty = 0
        
        # Calculate total
        total = price_usd * qty
        
        # Transform to target format
        result = {
            "id": str(product_id),
            "name": str(product_name),
            "total": total
        }
        
        return result
        
    except json.JSONDecodeError as e:
        return {"error": f"Invalid JSON: {e}"}
    except KeyError as e:
        return {"error": f"Missing field: {e}"}
    except Exception as e:
        return {"error": f"Transformation failed: {e}"}