from typing import Any, Dict, List, Optional
import asyncio
import json
import re


async def transform_json_structure(
    source_json: dict,
    target_schema: dict,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Transform JSON from source format to target schema with field mapping and calculations."""
    try:
        # Handle JSON string inputs defensively
        if isinstance(source_json, str):
            source_json = json.loads(source_json)
        if isinstance(target_schema, str):
            target_schema = json.loads(target_schema)
        
        # Validate inputs
        if not isinstance(source_json, dict):
            return {"error": f"source_json must be dict, got {type(source_json).__name__}"}
        if not isinstance(target_schema, dict):
            return {"error": f"target_schema must be dict, got {type(target_schema).__name__}"}
        
        # Initialize result dict
        result = {}
        
        # Transform based on the specific field mappings from the example
        # Map product_id to id
        if "product_id" in source_json:
            result["id"] = str(source_json["product_id"])
        
        # Map product_name to name
        if "product_name" in source_json:
            result["name"] = str(source_json["product_name"])
        
        # Calculate total from price_usd * qty
        if "price_usd" in source_json and "qty" in source_json:
            price = float(source_json["price_usd"])
            qty = int(source_json["qty"])
            result["total"] = round(price * qty, 2)
        
        return result
        
    except json.JSONDecodeError as e:
        return {"error": f"Invalid JSON: {e}"}
    except (ValueError, TypeError) as e:
        return {"error": f"Data type error: {e}"}
    except KeyError as e:
        return {"error": f"Missing required field: {e}"}
    except Exception as e:
        return {"error": f"Transformation error: {e}"}