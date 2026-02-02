from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel


class LineItem(BaseModel):
    """A single line item extracted from an invoice."""
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
    """Extracts line items from noisy OCR invoice text using LLM semantic understanding.
    
    The LLM analyzes the OCR text to identify and extract line items despite scanning
    artifacts, typos, and formatting inconsistencies that would break regex patterns.
    
    Args:
        ocr_text: The raw OCR text from a scanned invoice document that may contain
                  scanning artifacts, typos, and inconsistent formatting
    
    Returns:
        A JSON array of line item objects. Each line item has:
        - description (string): item/service description
        - quantity (number or null): number of units
        - unit_price (number or null): price per unit
        - total_price (number or null): line total
        Returns empty array [] if no line items can be confidently extracted.
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

For each line item found, extract:
- description: The item or service name/description (string)
- quantity: Number of units if present (number or null)
- unit_price: Price per unit if present (number or null)
- total_price: Total price for this line if present (number or null)

Return ONLY a valid JSON array. If no line items can be confidently extracted, return [].

Example output format:
[{{"description": "Office Supplies", "quantity": 5, "unit_price": 12.99, "total_price": 64.95}}, {{"description": "Consulting Services", "quantity": null, "unit_price": null, "total_price": 500.00}}]

OCR TEXT:
{text}

Return ONLY the JSON array, no other text:"""

    response = llm_client.generate(prompt)
    content = response.content.strip()
    
    # Extract JSON array from response (handles markdown code blocks)
    if "```" in content:
        # Extract content between code blocks
        json_match = re.search(r'```(?:json)?\s*(\[.*?\])\s*```', content, re.DOTALL)
        if json_match:
            content = json_match.group(1)
        else:
            # Try to find any JSON array
            array_match = re.search(r'\[.*\]', content, re.DOTALL)
            if array_match:
                content = array_match.group(0)
    else:
        # Try to find JSON array if not in code blocks
        array_match = re.search(r'\[.*\]', content, re.DOTALL)
        if array_match:
            content = array_match.group(0)
    
    # Parse and validate with Pydantic
    try:
        data = json.loads(content)
        
        if not isinstance(data, list):
            return []
        
        # Validate each line item with Pydantic
        validated_items = []
        for item in data:
            if isinstance(item, dict):
                try:
                    validated = LineItem(**item)
                    validated_items.append(validated.model_dump())
                except Exception:
                    # Skip invalid items but continue processing
                    continue
        
        return validated_items
        
    except json.JSONDecodeError:
        # If parsing fails, return empty array
        return []
