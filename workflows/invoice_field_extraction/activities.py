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
    """Extract structured invoice fields from document text.
    
    Uses LLM to parse unstructured billing memorandum text and extract key invoice 
    fields including vendor info, customer info, invoice metadata, and financial amounts.
    
    Args:
        document_text: The raw document text containing invoice/billing memorandum 
                       information with vendor details, customer name, dates, and 
                       amounts to extract
    
    Returns:
        Dict with extracted invoice fields: document_id, vendor_name, vendor_address,
        customer_name, customer_address, invoice_id, invoice_date, due_date,
        total_amount, tax_amount, currency. Returns empty string for fields not found.
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
    
    # This requires LLM because invoice text has complex, unstructured formatting
    # with varied layouts, mixed headers, addresses, and line items that need semantic understanding
    prompt = f"""Extract structured invoice data from the following document text.

Document text:
{document_text}

Extract the following fields and return ONLY valid JSON (no markdown, no explanation):
{{
  "document_id": "unique document identifier like taxpayer ID or reference number",
  "vendor_name": "company/firm name issuing the invoice",
  "vendor_address": "full address of the vendor",
  "customer_name": "name of the customer being billed",
  "customer_address": "address of the customer if available, empty string if not found",
  "invoice_id": "invoice or billing reference number",
  "invoice_date": "date of the invoice in original format from document",
  "due_date": "payment due date, empty string if not specified",
  "total_amount": "total amount due including currency symbol",
  "tax_amount": "tax amount if specified, empty string if not found",
  "currency": "currency code like USD"
}}

IMPORTANT:
- Return empty string "" for any field not found in the document
- Preserve exact wording and formatting from the document where applicable
- For vendor_name and vendor_address, extract exactly as shown in the document
- For amounts, include currency symbols if present
- Return ONLY the JSON object, nothing else"""

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
    
    # Parse the JSON response
    try:
        extracted = json.loads(content)
    except json.JSONDecodeError:
        # Return default empty structure if parsing fails
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
            "currency": ""
        }
    
    # Ensure all required fields are present with defaults
    return {
        "document_id": extracted.get("document_id", ""),
        "vendor_name": extracted.get("vendor_name", ""),
        "vendor_address": extracted.get("vendor_address", ""),
        "customer_name": extracted.get("customer_name", ""),
        "customer_address": extracted.get("customer_address", ""),
        "invoice_id": extracted.get("invoice_id", ""),
        "invoice_date": extracted.get("invoice_date", ""),
        "due_date": extracted.get("due_date", ""),
        "total_amount": extracted.get("total_amount", ""),
        "tax_amount": extracted.get("tax_amount", ""),
        "currency": extracted.get("currency", "")
    }
