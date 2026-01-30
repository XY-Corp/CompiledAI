from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel


class InvoiceData(BaseModel):
    """Schema for extracted invoice data."""
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


async def extract_invoice_fields(
    document_text: str,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extract structured invoice data fields from raw document text.
    
    Uses LLM to parse unstructured invoice document and extract key fields including
    vendor information, customer information, invoice identifiers, dates, and amounts.
    
    Args:
        document_text: The raw document text containing invoice information with vendor
                       details, customer details, line items, dates, and amounts to be extracted
    
    Returns:
        Dict with extracted invoice fields: document_id, vendor_name, vendor_address,
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
    
    # Invoice documents require LLM because OCR text has complex, unstructured formatting
    # with mixed headers, addresses, line items, and amounts that need semantic understanding
    prompt = f"""Extract structured invoice data from the following document text.

Document Text:
{document_text}

Extract the following fields and return ONLY valid JSON:
- document_id: unique identifier for the document (may be invoice number or reference ID)
- vendor_name: name of the vendor/seller company
- vendor_address: full address of the vendor
- customer_name: name of the customer/buyer
- customer_address: full address of the customer
- invoice_id: unique invoice number/identifier
- invoice_date: date the invoice was issued (keep original format from document)
- due_date: payment due date or payment terms
- total_amount: total amount due on the invoice (include currency symbol if present)
- tax_amount: tax amount if applicable, or empty string if not found
- currency: currency code (e.g., USD, EUR) - infer from symbols or text

Return ONLY valid JSON in this exact format:
{{"document_id": "value", "vendor_name": "value", "vendor_address": "value", "customer_name": "value", "customer_address": "value", "invoice_id": "value", "invoice_date": "value", "due_date": "value", "total_amount": "value", "tax_amount": "value", "currency": "value"}}

If a field cannot be found, use an empty string "".
Extract values exactly as they appear in the document."""

    # Call LLM to extract the data (llm_client.generate is SYNCHRONOUS - no await)
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
            json_match = re.search(r'\{[^{}]*\}', content, re.DOTALL)
            if json_match:
                content = json_match.group(0)
    
    # Parse and validate with Pydantic
    try:
        data = json.loads(content)
        validated = InvoiceData(**data)
        return validated.model_dump()
    except (json.JSONDecodeError, ValueError) as e:
        # If parsing fails, try to extract what we can with regex as fallback
        result = {
            "document_id": "",
            "vendor_name": "",
            "vendor_address": "",
            "customer_name": "",
            "customer_address": "",
            "invoice_id": "",
            "invoice_date": "",
            "due_date": "",
            "total_amount": "",
            "tax_amount": "",
            "currency": ""
        }
        
        # Try to extract invoice ID/number
        invoice_match = re.search(r'(?:invoice|inv)[#:\s]*([A-Za-z0-9\-]+)', document_text, re.IGNORECASE)
        if invoice_match:
            result["invoice_id"] = invoice_match.group(1)
            result["document_id"] = invoice_match.group(1)
        
        # Try to extract total amount
        total_match = re.search(r'(?:total|amount due|balance)[:\s]*\$?([\d,]+\.?\d*)', document_text, re.IGNORECASE)
        if total_match:
            result["total_amount"] = total_match.group(1)
        
        # Try to extract date
        date_match = re.search(r'(?:date|dated)[:\s]*(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})', document_text, re.IGNORECASE)
        if date_match:
            result["invoice_date"] = date_match.group(1)
        
        # Default currency to USD if dollar signs found
        if '$' in document_text:
            result["currency"] = "USD"
        
        return result
