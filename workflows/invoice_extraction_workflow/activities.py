from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel


class InvoiceFields(BaseModel):
    """Schema for extracted invoice fields."""
    document_id: str = ""
    vendor_name: str = ""
    vendor_address: str = ""
    customer_name: str = ""
    customer_address: str = ""
    invoice_id: str = ""
    invoice_date: str = ""
    due_date: str = ""
    total_amount: str = ""
    tax_amount: str = ""
    currency: str = ""


async def extract_invoice_fields(
    document_text: str,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extract structured invoice data from unstructured document text using LLM.
    
    The document text may contain various invoice formats with vendor name, address,
    customer information, invoice number, dates, and monetary amounts scattered throughout.
    This requires LLM because OCR invoice text has complex, unstructured formatting
    with mixed headers, addresses, and line items that need semantic understanding.
    
    Args:
        document_text: The raw document text containing invoice information including
                       vendor details, customer info, invoice numbers, dates, and 
                       amounts in various formats
    
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
    
    # Build a clear extraction prompt for the LLM
    # This requires LLM because OCR invoice text has complex, unstructured formatting
    # with mixed headers, addresses, and line items that need semantic understanding
    prompt = f"""Extract structured invoice/document data from the following document text.

Document Text:
{document_text}

Extract these fields and return as valid JSON:
- document_id: A unique identifier for the document (use invoice_id if no separate document ID)
- vendor_name: The name of the company/business issuing the invoice (preserve original formatting including line breaks)
- vendor_address: The full address of the vendor (preserve original formatting)
- customer_name: The name of the customer/recipient
- customer_address: The customer's address if available
- invoice_id: The invoice number/ID
- invoice_date: The date the invoice was issued
- due_date: Payment due date if available
- total_amount: The total amount due (number only, no currency symbol)
- tax_amount: Tax amount if specified (number only)
- currency: The currency code (USD, EUR, etc.)

For any field not found in the document, use an empty string "".
Preserve original text formatting including line breaks where they appear in the document.

Return ONLY valid JSON in this exact format:
{{"document_id": "...", "vendor_name": "...", "vendor_address": "...", "customer_name": "...", "customer_address": "...", "invoice_id": "...", "invoice_date": "...", "due_date": "...", "total_amount": "...", "tax_amount": "...", "currency": "..."}}"""

    # Call LLM for extraction (required for unstructured invoice text)
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
        validated = InvoiceFields(**data)
        return validated.model_dump()
    except (json.JSONDecodeError, ValueError) as e:
        # Return empty structure on parse failure
        return InvoiceFields().model_dump()
