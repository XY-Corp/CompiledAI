from typing import Any
import json
import re


async def extract_invoice_fields(
    ocr_text: str,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Uses LLM semantic understanding to extract structured invoice fields from noisy OCR text.
    
    Handles OCR artifacts, typos, and formatting inconsistencies. Returns null for fields
    that cannot be confidently extracted.
    
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

Extract these fields (use null if not found or unclear):
1. document_id: Invoice number, receipt number, or document ID
2. vendor_name: Seller/vendor company name
3. customer_name: Buyer/customer name
4. invoice_date: Invoice date (keep original format)
5. due_date: Payment due date (keep original format)
6. total_amount: Total amount as a number only (no currency symbols, e.g., 1234.56)
7. tax_amount: Tax amount as a number only (no currency symbols)
8. currency: Currency code (USD, EUR, GBP, etc.)

Return ONLY valid JSON in this exact format:
{{"document_id": "INV-123" or null, "vendor_name": "Company Name" or null, "customer_name": "Customer Name" or null, "invoice_date": "2024-01-15" or null, "due_date": "2024-02-15" or null, "total_amount": 1234.56 or null, "tax_amount": 123.45 or null, "currency": "USD" or null}}"""

    response = llm_client.generate(prompt)
    content = response.content.strip()
    
    # Extract JSON from response (handles markdown code blocks)
    if "```" in content:
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
        if json_match:
            content = json_match.group(1)
        else:
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                content = json_match.group(0)
    
    # Parse the response
    try:
        extracted = json.loads(content)
        
        # Build result with validated types
        result = {
            "document_id": extracted.get("document_id") if isinstance(extracted.get("document_id"), str) else None,
            "vendor_name": extracted.get("vendor_name") if isinstance(extracted.get("vendor_name"), str) else None,
            "customer_name": extracted.get("customer_name") if isinstance(extracted.get("customer_name"), str) else None,
            "invoice_date": extracted.get("invoice_date") if isinstance(extracted.get("invoice_date"), str) else None,
            "due_date": extracted.get("due_date") if isinstance(extracted.get("due_date"), str) else None,
            "total_amount": None,
            "tax_amount": None,
            "currency": extracted.get("currency") if isinstance(extracted.get("currency"), str) else None
        }
        
        # Handle numeric fields - convert to float if possible
        total = extracted.get("total_amount")
        if total is not None:
            if isinstance(total, (int, float)):
                result["total_amount"] = float(total)
            elif isinstance(total, str):
                # Try to parse string as number
                try:
                    cleaned = re.sub(r'[^\d.\-]', '', total)
                    result["total_amount"] = float(cleaned) if cleaned else None
                except (ValueError, TypeError):
                    result["total_amount"] = None
        
        tax = extracted.get("tax_amount")
        if tax is not None:
            if isinstance(tax, (int, float)):
                result["tax_amount"] = float(tax)
            elif isinstance(tax, str):
                try:
                    cleaned = re.sub(r'[^\d.\-]', '', tax)
                    result["tax_amount"] = float(cleaned) if cleaned else None
                except (ValueError, TypeError):
                    result["tax_amount"] = None
        
        return result
        
    except json.JSONDecodeError:
        # If LLM response isn't valid JSON, return null response
        return null_response
