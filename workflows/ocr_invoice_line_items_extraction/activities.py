from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel


class LineItem(BaseModel):
    """Schema for a single invoice line item."""
    description: str
    quantity: Optional[float] = None
    unit_price: Optional[float] = None
    total_price: Optional[float] = None


class ExtractedLineItems(BaseModel):
    """Schema for extracted line items response."""
    line_items: List[LineItem]


async def extract_invoice_line_items(
    ocr_text: str,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extract line items from noisy OCR invoice text using LLM semantic understanding.
    
    The OCR text contains scanning artifacts and formatting issues that require 
    intelligent parsing rather than regex. Returns a JSON array of line items.
    
    Args:
        ocr_text: The raw OCR-scanned invoice text containing potential scanning artifacts,
                  typos, and inconsistent formatting that needs semantic understanding to parse
    
    Returns:
        Dict with 'line_items' containing an array of extracted invoice line items.
        Each line item has: 'description' (string), 'quantity' (number or null),
        'unit_price' (number or null), 'total_price' (number or null).
        Returns empty array if no items can be confidently extracted.
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
- description: The item or service description (required)
- quantity: Number of units (null if not found or unclear)
- unit_price: Price per unit (null if not found or unclear)
- total_price: Total price for the line (null if not found or unclear)

OCR TEXT:
{text}

Return ONLY valid JSON in this exact format (no markdown, no explanation):
{{"line_items": [{{"description": "item description here", "quantity": 2, "unit_price": 10.50, "total_price": 21.00}}]}}

If a numeric value is unclear or missing, use null instead of guessing.
If no line items can be confidently identified, return: {{"line_items": []}}"""

    # Call LLM for semantic extraction (synchronous call - no await)
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
    
    # Parse and validate with Pydantic
    try:
        data = json.loads(content)
        
        # Validate structure
        if not isinstance(data, dict) or "line_items" not in data:
            return {"line_items": []}
        
        raw_items = data.get("line_items", [])
        if not isinstance(raw_items, list):
            return {"line_items": []}
        
        # Validate and normalize each line item
        validated_items = []
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            
            # Description is required
            description = item.get("description")
            if not description or not isinstance(description, str) or not description.strip():
                continue
            
            # Build validated item
            validated_item = {
                "description": description.strip(),
                "quantity": None,
                "unit_price": None,
                "total_price": None
            }
            
            # Validate numeric fields (allow null)
            for field in ["quantity", "unit_price", "total_price"]:
                value = item.get(field)
                if value is not None:
                    try:
                        # Handle string numbers and actual numbers
                        if isinstance(value, (int, float)):
                            validated_item[field] = float(value) if '.' in str(value) or field != "quantity" else value
                        elif isinstance(value, str):
                            # Try to parse as number
                            cleaned = re.sub(r'[^\d.\-]', '', value)
                            if cleaned:
                                validated_item[field] = float(cleaned)
                    except (ValueError, TypeError):
                        pass  # Keep as null
            
            validated_items.append(validated_item)
        
        return {"line_items": validated_items}
        
    except json.JSONDecodeError:
        # If JSON parsing fails, return empty array
        return {"line_items": []}
    except Exception:
        # Catch-all for unexpected errors
        return {"line_items": []}
