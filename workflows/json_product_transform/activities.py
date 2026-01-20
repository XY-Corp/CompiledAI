from typing import Any, Dict, List, Optional
import json


async def transform_product_json(
    source_data: dict,
    schema_definition: dict,
    # Injected context (always include)
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Transform product JSON from source format to target format by mapping fields and calculating total value."""
    
    try:
        # Parse JSON strings if needed (defensive input handling)
        if isinstance(source_data, str):
            source_data = json.loads(source_data)
        if isinstance(schema_definition, str):
            schema_definition = json.loads(schema_definition)
        
        # Validate input types
        if not isinstance(source_data, dict):
            return {"error": f"source_data must be dict, got {type(source_data).__name__}"}
        if not isinstance(schema_definition, dict):
            return {"error": f"schema_definition must be dict, got {type(schema_definition).__name__}"}
        
        # Extract source fields with defaults
        product_id = source_data.get('product_id', '')
        product_name = source_data.get('product_name', '')
        price_usd = source_data.get('price_usd', 0)
        qty = source_data.get('qty', 0)
        
        # Convert to proper types
        try:
            price = float(price_usd)
            quantity = float(qty)
        except (ValueError, TypeError):
            price = 0.0
            quantity = 0.0
        
        # Calculate total value
        total_value = price * quantity
        
        # Transform to target format based on schema
        # Map fields according to the expected output schema
        transformed = {
            "id": str(product_id),
            "name": str(product_name),
            "total": round(total_value, 2)  # Round to 2 decimal places for currency
        }
        
        return transformed
        
    except json.JSONDecodeError as e:
        return {"error": f"Invalid JSON: {e}"}
    except KeyError as e:
        return {"error": f"Missing required field: {e}"}
    except Exception as e:
        return {"error": f"Transformation failed: {e}"}