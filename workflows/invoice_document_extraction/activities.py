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


async def extract_invoice_fields(
    document_text: str,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extracts all required invoice fields from the raw document text using LLM-based information extraction.
    
    The document contains wire instructions, vendor details, customer information, invoice metadata,
    and financial amounts that need to be parsed and structured.
    
    Args:
        document_text: The raw unstructured document text containing invoice information including
                       wire instructions, vendor name and address, customer details, invoice ID,
                       date, amounts, and other billing information
    
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
    # This requires LLM because invoice documents have complex, unstructured formatting
    # with mixed headers, addresses, wire instructions, and line items that need semantic understanding
    prompt = f"""Extract structured invoice data from the following document text.

Return ONLY valid JSON with these exact fields:
{{
    "document_id": "unique identifier like study number, PO number, or reference number",
    "vendor_name": "company name issuing the invoice",
    "vendor_address": "full vendor mailing address on one line",
    "customer_name": "company being billed / bill to name",
    "customer_address": "full customer/bill-to address on one line",
    "invoice_id": "invoice number",
    "invoice_date": "invoice date in original format",
    "due_date": "payment due date or payment terms like 'Net 30'",
    "total_amount": "total amount due as string with currency symbol if present",
    "tax_amount": "tax amount if applicable, or empty string if not found",
    "currency": "payment currency code like USD, EUR, etc."
}}

Document text:
{document_text}

Return ONLY the JSON object, no markdown or explanation."""

    # Use LLM for extraction - this is appropriate because invoice documents
    # are unstructured with varying formats that require semantic understanding
    response = llm_client.generate(prompt)
    
    # Extract JSON from response (handles markdown code blocks)
    content = response.content.strip()
    
    # Remove markdown code blocks if present
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
        validated = InvoiceFields(**data)
        return validated.model_dump()
    except (json.JSONDecodeError, ValueError) as e:
        # Return error structure matching schema with empty strings
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
            "tax_amount": "",
            "currency": "",
        }
