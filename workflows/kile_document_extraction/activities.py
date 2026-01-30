from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel


class InvoiceFields(BaseModel):
    """Schema for extracted invoice fields."""
    document_id: str
    vendor_name: str
    vendor_address: str
    customer_name: str
    customer_address: str
    invoice_id: str
    invoice_date: str
    due_date: str
    total_amount: str
    tax_amount: str
    currency: str


async def extract_document_fields(
    document_text: str,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extract structured invoice/document fields from OCR-scanned document text.
    
    This includes vendor information, customer information, invoice metadata (ID, dates),
    and financial amounts. Uses LLM for extraction since OCR text has complex, unstructured
    formatting with mixed headers, addresses, and line items that require semantic understanding.
    
    Args:
        document_text: The raw OCR-scanned document text containing invoice/document information
                       with vendor name, addresses, dates, amounts, and other relevant fields
    
    Returns:
        Dict with extracted document fields: document_id, vendor_name, vendor_address,
        customer_name, customer_address, invoice_id, invoice_date, due_date,
        total_amount, tax_amount, currency
    """
    # Handle JSON string input defensively
    if isinstance(document_text, str):
        try:
            parsed = json.loads(document_text)
            if isinstance(parsed, dict) and "text" in parsed:
                document_text = parsed["text"]
            elif isinstance(parsed, dict) and "document_text" in parsed:
                document_text = parsed["document_text"]
            elif isinstance(parsed, str):
                document_text = parsed
        except json.JSONDecodeError:
            pass  # It's already a plain string
    
    # Build extraction prompt for LLM
    # OCR invoice text has complex, unstructured formatting requiring semantic understanding
    prompt = f"""Extract structured invoice data from the following OCR-scanned document text.

Return ONLY a valid JSON object with these exact fields:
- document_id: unique document/invoice identifier (look for invoice #, document #, or similar)
- vendor_name: company/organization issuing the document (seller/provider name)
- vendor_address: full street address of vendor (may span multiple lines)
- customer_name: name of person/company receiving goods/services (buyer/bill to)
- customer_address: full street address of customer (may span multiple lines)
- invoice_id: invoice reference number (same as document_id if only one identifier)
- invoice_date: date invoice was issued in MM/DD/YY format
- due_date: payment due date in MM/DD/YY format
- total_amount: total amount due as string with decimals (e.g., "1234.56")
- tax_amount: tax amount as string with decimals (e.g., "0.00" if not found)
- currency: currency code like USD (default to "USD" if not specified)

For any field not found in the document, use empty string "" (except currency which defaults to "USD").
For dates, convert to MM/DD/YY format if found in different format.
For amounts, extract numeric value with decimals as a string.

Document text:
{document_text}

Return ONLY the JSON object, no markdown or explanation."""

    # Use LLM to extract fields (OCR text requires semantic understanding)
    response = llm_client.generate(prompt)
    content = response.content.strip()
    
    # Extract JSON from response (handles markdown code blocks)
    if "```" in content:
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
        
        # Ensure all required fields exist with defaults
        defaults = {
            "document_id": "",
            "vendor_name": "",
            "vendor_address": "",
            "customer_name": "",
            "customer_address": "",
            "invoice_id": "",
            "invoice_date": "",
            "due_date": "",
            "total_amount": "",
            "tax_amount": "0.00",
            "currency": "USD"
        }
        
        for key, default_value in defaults.items():
            if key not in data or data[key] is None:
                data[key] = default_value
            # Ensure all values are strings
            data[key] = str(data[key]) if data[key] is not None else default_value
        
        # If invoice_id is empty but document_id exists, use document_id
        if not data["invoice_id"] and data["document_id"]:
            data["invoice_id"] = data["document_id"]
        # Vice versa
        if not data["document_id"] and data["invoice_id"]:
            data["document_id"] = data["invoice_id"]
        
        # Validate with Pydantic
        validated = InvoiceFields(**data)
        return validated.model_dump()
        
    except (json.JSONDecodeError, ValueError) as e:
        # Return empty structure on parse error
        return {
            "document_id": "",
            "vendor_name": "",
            "vendor_address": "",
            "customer_name": "",
            "customer_address": "",
            "invoice_id": "",
            "invoice_date": "",
            "due_date": "",
            "total_amount": "",
            "tax_amount": "0.00",
            "currency": "USD"
        }
