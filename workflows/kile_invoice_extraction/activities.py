from typing import Any, Dict, List, Optional
import json
import re


async def extract_invoice_fields(
    document_text: str,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extract structured invoice data from document text.
    
    Parses semi-structured OCR text to identify and extract: document_id (often labeled 
    as Appud or Document#), vendor_name and vendor_address, customer_name and customer_address,
    invoice_id (invoice number), invoice_date, due_date (from payment terms), total_amount,
    tax_amount, and currency. Returns empty string for fields not found in the document.
    
    Args:
        document_text: The raw document text containing invoice information, typically from OCR.
                       May include headers, addresses, line items, and payment terms in 
                       semi-structured format
    
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
    
    # Build extraction prompt for LLM
    # OCR invoice text has complex, unstructured formatting requiring semantic understanding
    prompt = f"""Extract structured invoice data from the following OCR-scanned document text.

Return a JSON object with these exact fields (use empty string "" for fields not found):
- document_id: The unique document identifier, often labeled as "Appud", "Document#", "Doc#", or similar
- vendor_name: The name of the vendor/supplier company
- vendor_address: The full address of the vendor (may span multiple lines)
- customer_name: The name of the customer/recipient
- customer_address: The full address of the customer (may span multiple lines)
- invoice_id: The invoice number
- invoice_date: The date the invoice was issued
- due_date: The payment due date or payment terms
- total_amount: The total invoice amount (just the number, without currency symbol if possible)
- tax_amount: The tax amount if applicable (just the number)
- currency: The currency code (e.g., USD, EUR) - infer from symbols like $ or explicit mentions

Document text:
{document_text}

Return ONLY valid JSON in this exact format:
{{"document_id": "...", "vendor_name": "...", "vendor_address": "...", "customer_name": "...", "customer_address": "...", "invoice_id": "...", "invoice_date": "...", "due_date": "...", "total_amount": "...", "tax_amount": "...", "currency": "..."}}"""

    # Use LLM for extraction - OCR text requires semantic understanding
    response = llm_client.generate(prompt)
    
    # Parse LLM response
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
    
    # Default result with empty strings
    default_result = {
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
    
    try:
        data = json.loads(content)
        # Ensure all required fields are present, use empty string for missing
        result = {}
        for field in default_result.keys():
            value = data.get(field, "")
            # Ensure value is a string
            if value is None:
                value = ""
            result[field] = str(value)
        return result
    except json.JSONDecodeError:
        # If JSON parsing fails, return defaults
        return default_result
