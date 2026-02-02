from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel


class InvoiceFields(BaseModel):
    """Pydantic model for validating LLM-extracted invoice fields."""
    document_id: Optional[str] = None
    vendor_name: Optional[str] = None
    customer_name: Optional[str] = None
    invoice_date: Optional[str] = None
    due_date: Optional[str] = None
    total_amount: Optional[float] = None
    tax_amount: Optional[float] = None
    currency: Optional[str] = None


async def extract_invoice_fields(
    ocr_text: str,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Uses LLM semantic understanding to extract structured invoice fields from noisy OCR text.
    
    Handles OCR artifacts, typos, and formatting inconsistencies that would break regex patterns.
    Returns null for fields that cannot be confidently extracted.
    
    Args:
        ocr_text: The raw OCR-scanned document text containing invoice information with
                  potential scanning artifacts, typos, and inconsistent formatting
    
    Returns:
        Dict with extracted invoice fields: document_id, vendor_name, customer_name,
        invoice_date, due_date, total_amount, tax_amount, currency. All fields return
        null if not confidently extractable.
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
    
    # Default null response structure
    null_response = {
        "document_id": None,
        "vendor_name": None,
        "customer_name": None,
        "invoice_date": None,
        "due_date": None,
        "total_amount": None,
        "tax_amount": None,
        "currency": None
    }
    
    # Return nulls if no valid input
    if not ocr_text or not isinstance(ocr_text, str) or not ocr_text.strip():
        return null_response
    
    text = ocr_text.strip()
    
    # Use LLM for semantic extraction - OCR text is noisy with scanning artifacts,
    # typos, merged characters, inconsistent spacing. Regex would fail on:
    # - "lnvoice" instead of "Invoice"
    # - "S 1,234.56" instead of "$1,234.56"
    # - "Tota1" instead of "Total"
    # - Random line breaks in the middle of values
    # - Garbled vendor/customer names
    prompt = f"""Extract invoice/receipt fields from this noisy OCR-scanned text. The text may contain scanning artifacts, typos, and inconsistent formatting.

OCR Text:
{text}

Extract the following fields. Return null for any field you cannot confidently identify:
- document_id: invoice number, receipt number, or document ID
- vendor_name: seller/vendor company name
- customer_name: buyer/customer name or company
- invoice_date: the invoice or receipt date (any format)
- due_date: payment due date (any format)
- total_amount: total amount as a number (no currency symbol)
- tax_amount: tax amount as a number (no currency symbol)
- currency: currency code (USD, EUR, GBP, etc.)

Return ONLY valid JSON in this exact format:
{{"document_id": "value or null", "vendor_name": "value or null", "customer_name": "value or null", "invoice_date": "value or null", "due_date": "value or null", "total_amount": number or null, "tax_amount": number or null, "currency": "value or null"}}"""

    try:
        # Call LLM for semantic extraction (synchronous - no await)
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
        
        # Parse JSON response
        data = json.loads(content)
        
        # Validate and normalize with Pydantic
        validated = InvoiceFields(**data)
        
        return validated.model_dump()
        
    except (json.JSONDecodeError, ValueError) as e:
        # If LLM response parsing fails, return null response
        return null_response
    except Exception as e:
        # For any other error, return null response
        return null_response
