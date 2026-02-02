from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel


class LineItem(BaseModel):
    """Schema for a single line item extracted from invoice."""
    description: str
    quantity: Optional[float] = None
    unit_price: Optional[float] = None
    total_price: Optional[float] = None


async def extract_invoice_line_items(
    ocr_text: str,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> list[dict[str, Any]]:
    """Uses LLM semantic understanding to extract line items from noisy OCR-scanned invoice text.
    
    Handles scanning artifacts, typos, and inconsistent formatting. Returns a JSON array
    of line items with description, quantity, unit_price, and total_price fields.
    
    Args:
        ocr_text: The raw OCR-scanned invoice text that may contain scanning artifacts,
                  typos, and inconsistent formatting. Contains invoice headers, line items
                  with descriptions and prices, and other invoice metadata.
    
    Returns:
        A JSON array of line item objects extracted from the OCR text. Each line item has:
        description (str), quantity (number or null), unit_price (number or null),
        total_price (number or null). Returns empty array [] if no line items can be
        confidently extracted.
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
        return []
    
    text = ocr_text.strip()
    
    # Use LLM for semantic extraction - OCR text is noisy with scanning artifacts,
    # typos, merged characters, inconsistent spacing. Regex would fail on:
    # - "Qty" vs "Quantity" vs "Units" vs garbled characters
    # - Decimal points confused with periods
    # - Inconsistent column alignments
    # - Missing or merged values
    # - Currency symbols mangled by OCR
    prompt = f"""Extract line items from this noisy OCR-scanned invoice text. The text may contain scanning artifacts, typos, and inconsistent formatting.

For each line item, extract:
- description: The item/service description (required, string)
- quantity: Number of units if identifiable (number or null)
- unit_price: Price per unit if identifiable (number or null)
- total_price: Line total if identifiable (number or null)

Return ONLY a valid JSON array of objects. Each object must have description, quantity, unit_price, and total_price fields.
If a numeric field cannot be determined, use null.
If no line items can be confidently extracted, return an empty array [].

Example output format:
[{{"description": "Widget Assembly Kit", "quantity": 5, "unit_price": 29.99, "total_price": 149.95}}, {{"description": "Professional Services", "quantity": null, "unit_price": null, "total_price": 275.00}}]

OCR TEXT:
{text}

Return ONLY the JSON array, no other text:"""

    response = llm_client.generate(prompt)
    content = response.content.strip()
    
    # Extract JSON array from response (handles markdown code blocks)
    if "```" in content:
        # Extract content between ```json and ``` or between ``` and ```
        json_match = re.search(r'```(?:json)?\s*(\[.*?\])\s*```', content, re.DOTALL)
        if json_match:
            content = json_match.group(1)
        else:
            # Try to find any JSON array
            json_match = re.search(r'\[.*\]', content, re.DOTALL)
            if json_match:
                content = json_match.group(0)
    
    # Parse and validate the response
    try:
        data = json.loads(content)
        
        if not isinstance(data, list):
            return []
        
        # Validate and clean each line item
        validated_items = []
        for item in data:
            if not isinstance(item, dict):
                continue
            
            # Ensure description exists
            description = item.get("description", "")
            if not description or not isinstance(description, str):
                continue
            
            # Parse and validate numeric fields
            def parse_number(value):
                if value is None:
                    return None
                if isinstance(value, (int, float)):
                    return float(value)
                if isinstance(value, str):
                    # Try to extract number from string (handles "$29.99", "29.99 USD", etc.)
                    match = re.search(r'[\d,]+\.?\d*', value.replace(',', ''))
                    if match:
                        try:
                            return float(match.group(0))
                        except ValueError:
                            return None
                return None
            
            validated_item = {
                "description": description.strip(),
                "quantity": parse_number(item.get("quantity")),
                "unit_price": parse_number(item.get("unit_price")),
                "total_price": parse_number(item.get("total_price"))
            }
            validated_items.append(validated_item)
        
        return validated_items
        
    except json.JSONDecodeError:
        # If parsing fails, return empty array
        return []
