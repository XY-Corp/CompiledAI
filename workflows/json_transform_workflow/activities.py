from typing import Any, Dict, List, Optional
import json


async def transform_product_data(
    source_data: dict,
    schema_spec: dict,
    # Injected context (always include)
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Transform product JSON from source format to target schema with field mapping and total calculation."""
    try:
        # Handle JSON string inputs defensively
        if isinstance(source_data, str):
            source_data = json.loads(source_data)
        if isinstance(schema_spec, str):
            schema_spec = json.loads(schema_spec)
        
        # Validate inputs are dictionaries
        if not isinstance(source_data, dict):
            return {"error": f"source_data must be dict, got {type(source_data).__name__}"}
        if not isinstance(schema_spec, dict):
            return {"error": f"schema_spec must be dict, got {type(schema_spec).__name__}"}
        
        # Transform product data using field mapping and calculations
        # Map id from product_id
        product_id = source_data.get('product_id', '')
        if not product_id:
            return {"error": "Missing product_id in source_data"}
        
        # Map name from product_name
        product_name = source_data.get('product_name', '')
        if not product_name:
            return {"error": "Missing product_name in source_data"}
        
        # Calculate total as price_usd * qty
        price_usd = source_data.get('price_usd', 0)
        qty = source_data.get('qty', 0)
        
        # Ensure numeric values
        try:
            price_usd = float(price_usd) if price_usd else 0.0
            qty = float(qty) if qty else 0.0
        except (ValueError, TypeError):
            return {"error": "price_usd and qty must be numeric values"}
        
        total = price_usd * qty
        
        # Return transformed data in exact target format
        transformed = {
            "id": str(product_id),
            "name": str(product_name),
            "total": round(total, 2)  # Round to 2 decimal places for currency
        }
        
        return transformed
        
    except json.JSONDecodeError as e:
        return {"error": f"Invalid JSON: {e}"}
    except KeyError as e:
        return {"error": f"Missing required field: {e}"}
    except Exception as e:
        return {"error": f"Transformation failed: {str(e)}"}