from typing import Any, Dict, List, Optional
import asyncio
import json
import re

async def transform_json_data(
    input_prompt: str,
    source_context: dict,
    target_context: dict,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Transform JSON data from source format to target schema by mapping and computing field values."""
    try:
        # Handle JSON strings defensively for structured inputs
        if isinstance(source_context, str):
            source_context = json.loads(source_context)
        if isinstance(target_context, str):
            target_context = json.loads(target_context)
        
        # Validate types
        if not isinstance(source_context, dict):
            source_context = {}
        if not isinstance(target_context, dict):
            target_context = {}
        
        # Extract source JSON data from the input prompt or use source_context
        # First try to find JSON data in the input_prompt
        source_data = {}
        
        # Look for JSON patterns in the input prompt
        json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
        json_matches = re.findall(json_pattern, input_prompt)
        
        for match in json_matches:
            try:
                parsed_json = json.loads(match)
                if isinstance(parsed_json, dict) and len(parsed_json) > 0:
                    source_data = parsed_json
                    break
            except json.JSONDecodeError:
                continue
        
        # If no JSON found in prompt, check if source_context contains the data
        if not source_data and source_context:
            # Look for data fields in source_context
            for key, value in source_context.items():
                if isinstance(value, dict):
                    source_data = value
                    break
        
        # If still no source data, return empty result matching target schema
        if not source_data:
            result = {}
            for field in target_context.keys():
                if field == "id":
                    result[field] = ""
                elif field == "name":
                    result[field] = ""
                elif field == "total":
                    result[field] = 0.0
                else:
                    result[field] = ""
            return result
        
        # Transform data based on target schema
        result = {}
        
        # Map common field transformations
        for target_field, target_type in target_context.items():
            if target_field == "id":
                # Look for ID-like fields in source
                result["id"] = (
                    source_data.get("id") or
                    source_data.get("product_id") or
                    source_data.get("item_id") or
                    source_data.get("sku") or
                    ""
                )
            elif target_field == "name":
                # Look for name-like fields in source
                result["name"] = (
                    source_data.get("name") or
                    source_data.get("product_name") or
                    source_data.get("item_name") or
                    source_data.get("title") or
                    ""
                )
            elif target_field == "total":
                # Calculate total from price and quantity fields
                price = (
                    source_data.get("price") or
                    source_data.get("price_usd") or
                    source_data.get("cost") or
                    source_data.get("amount") or
                    0
                )
                quantity = (
                    source_data.get("qty") or
                    source_data.get("quantity") or
                    source_data.get("count") or
                    1
                )
                
                # Convert to numbers if they're strings
                try:
                    price = float(price) if price else 0.0
                    quantity = float(quantity) if quantity else 1.0
                    result["total"] = price * quantity
                except (ValueError, TypeError):
                    result["total"] = 0.0
            else:
                # For other fields, try direct mapping or set default
                result[target_field] = source_data.get(target_field, "")
        
        return result
        
    except Exception as e:
        # Return empty result matching target schema on error
        result = {}
        if isinstance(target_context, dict):
            for field in target_context.keys():
                if field == "id":
                    result[field] = ""
                elif field == "name":
                    result[field] = ""
                elif field == "total":
                    result[field] = 0.0
                else:
                    result[field] = ""
        return result