from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel, Field


class LineItem(BaseModel):
    """A single line item from an invoice."""
    description: str = Field(..., description="Item or service description")
    quantity: Optional[float] = Field(None, description="Units/quantity")
    unit_price: Optional[float] = Field(None, description="Price per unit")
    total_price: Optional[float] = Field(None, description="Line total")


async def extract_invoice_line_items(
    ocr_text: str,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Use LLM to extract line items from noisy OCR invoice text.
    
    The LLM performs semantic understanding to handle OCR artifacts, typos, and 
    inconsistent formatting that would break regex patterns. Returns a JSON structure
    with line items array.
    
    Args:
        ocr_text: The raw OCR-scanned invoice text containing potential line items
                  with scanning artifacts, typos, and inconsistent formatting
    
    Returns:
        Dict with 'line_items' field containing an array where each item has:
        description (string), quantity (number or null), unit_price (number or null),
        total_price (number or null). Returns empty array [] if no line items found.
    """
    # Handle JSON string input defensively
    if isinstance(ocr_text, str):
        try:
            parsed = json.loads(ocr_text)
            if isinstance(parsed, dict) and "ocr_text" in parsed:
                ocr_text = parsed["ocr_text"]
            elif isinstance(parsed, dict) and "text" in parsed:
                ocr_text = parsed["text"]
            elif isinstance(parsed, str):
                ocr_text = parsed
        except json.JSONDecodeError:
            pass  # It's already a plain string
    
    # Return empty array if no valid input
    if not ocr_text or not isinstance(ocr_text, str) or not ocr_text.strip():
        return {"line_items": []}
    
    text = ocr_text.strip()
    
    # Use LLM for semantic extraction - OCR text is noisy with scanning artifacts,
    # typos, merged characters, inconsistent spacing. Regex would fail on:
    # - "Qty" vs "Quantity" vs "Units" vs garbled characters
    # - Decimal points confused with periods
    # - Inconsistent column alignments
    # - Missing or merged values
    # - Currency symbols mangled by OCR
    prompt = f"""Extract line items from this noisy OCR-scanned invoice text. The text may contain scanning artifacts, typos, and inconsistent formatting.

For each line item found, extract:
- description: the item or service description (required)
- quantity: number of units (null if not found or unclear)
- unit_price: price per unit (null if not found or unclear)
- total_price: line total price (null if not found or unclear)

Return ONLY valid JSON in this exact format (no markdown, no explanation):
{{"line_items": [{{"description": "Item name", "quantity": 2, "unit_price": 10.00, "total_price": 20.00}}]}}

Use null for any numeric field that cannot be confidently determined.
Return {{"line_items": []}} if no line items can be confidently extracted.

OCR TEXT:
{text}"""

    response = llm_client.generate(prompt)
    content = response.content.strip()
    
    # Extract JSON from response (handles markdown code blocks)
    if "```" in content:
        # Extract content between ```json and ``` or between ``` and ```
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
        if json_match:
            content = json_match.group(1)
        else:
            # Try to find any JSON object
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                content = json_match.group(0)
    
    # Parse and validate response
    try:
        data = json.loads(content)
        
        # Ensure we have the expected structure
        if not isinstance(data, dict) or "line_items" not in data:
            # Try to wrap if it's just an array
            if isinstance(data, list):
                data = {"line_items": data}
            else:
                return {"line_items": []}
        
        line_items = data.get("line_items", [])
        
        if not isinstance(line_items, list):
            return {"line_items": []}
        
        # Validate and normalize each line item
        validated_items = []
        for item in line_items:
            if not isinstance(item, dict):
                continue
            
            # Description is required
            description = item.get("description")
            if not description or not isinstance(description, str) or not description.strip():
                continue
            
            # Build validated item with proper types
            validated_item = {
                "description": description.strip(),
                "quantity": None,
                "unit_price": None,
                "total_price": None
            }
            
            # Parse numeric fields, allowing null
            for field in ["quantity", "unit_price", "total_price"]:
                value = item.get(field)
                if value is not None:
                    try:
                        if isinstance(value, (int, float)):
                            validated_item[field] = float(value) if value != int(value) else value
                        elif isinstance(value, str):
                            # Try to parse numeric string
                            clean_val = re.sub(r'[^\d.\-]', '', value)
                            if clean_val:
                                validated_item[field] = float(clean_val)
                    except (ValueError, TypeError):
                        pass  # Keep as None
            
            validated_items.append(validated_item)
        
        return {"line_items": validated_items}
        
    except json.JSONDecodeError:
        # If LLM response isn't valid JSON, return empty
        return {"line_items": []}
