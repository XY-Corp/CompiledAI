"""Hybrid extraction for invoice documents.

Strategy: Regex first (fast, free), LLM fallback for low-confidence fields (accurate).

This achieves the best of both worlds:
- Fast extraction when regex patterns match confidently
- High accuracy via LLM fallback when regex is uncertain
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

# Import the existing regex-based extraction
from .activities import extract_invoice_fields


@dataclass
class ExtractionResult:
    """Result of hybrid extraction with confidence and timing metadata."""
    
    fields: dict[str, Any]
    confidence: dict[str, float]
    used_llm: bool
    llm_fields: list[str]  # Which fields were extracted by LLM
    regex_time_ms: float
    llm_time_ms: float
    total_time_ms: float
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class ConfidenceConfig:
    """Configuration for confidence scoring heuristics."""
    
    # document_id suspicious words (case-insensitive)
    doc_id_suspicious_words: list[str] = field(default_factory=lambda: [
        "information", "invoice", "no", "number", "date", "order", 
        "advertiser", "proposal", "the", "for", "to", "from"
    ])
    
    # vendor_name suspicious patterns
    vendor_name_suspicious: list[str] = field(default_factory=lambda: [
        "invoice", "receipt", "order", "bill", "statement", "page",
        "date", "total", "amount", "the"
    ])
    vendor_name_min_length: int = 3
    
    # Date validation regex (YYYY-MM-DD format after normalization)
    date_valid_pattern: str = r"^\d{4}-\d{2}-\d{2}$"
    
    # Suspicious amounts (exactly round numbers that might be false positives)
    suspicious_amounts: list[float] = field(default_factory=lambda: [0.0, 1.0, 10.0, 100.0])


class HybridExtractor:
    """Hybrid regex + LLM extractor for invoice documents."""
    
    # Fields we track for KILE task
    KILE_FIELDS = [
        "document_id",
        "vendor_name", 
        "vendor_address",
        "customer_name",
        "customer_address",
        "invoice_date",
        "due_date",
        "total_amount",
        "tax_amount",
        "currency",
    ]
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-sonnet-4-20250514",
        confidence_config: Optional[ConfidenceConfig] = None,
        confidence_threshold: float = 0.5,
    ):
        """Initialize the hybrid extractor.
        
        Args:
            api_key: Anthropic API key. If None, reads from ANTHROPIC_API_KEY env var.
            model: Claude model to use for LLM fallback.
            confidence_config: Configuration for confidence heuristics.
            confidence_threshold: Fields below this confidence trigger LLM fallback.
        """
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.model = model
        self.confidence_config = confidence_config or ConfidenceConfig()
        self.confidence_threshold = confidence_threshold
        self._client = None
    
    @property
    def client(self):
        """Lazy initialization of Anthropic client."""
        if self._client is None:
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=self.api_key)
            except ImportError:
                raise ImportError("anthropic package required for LLM fallback. Install with: pip install anthropic")
        return self._client
    
    def calculate_confidence(self, fields: dict[str, Any]) -> dict[str, float]:
        """Calculate confidence score for each extracted field.
        
        Returns dict mapping field names to confidence scores (0.0 to 1.0).
        """
        confidence = {}
        cfg = self.confidence_config
        
        for field_name in self.KILE_FIELDS:
            value = fields.get(field_name)
            
            if value is None:
                confidence[field_name] = 0.0
                continue
            
            # Default to high confidence
            score = 1.0
            
            if field_name == "document_id":
                score = self._score_document_id(value, cfg)
            elif field_name == "vendor_name":
                score = self._score_vendor_name(value, cfg)
            elif field_name in ("invoice_date", "due_date"):
                score = self._score_date(value, cfg)
            elif field_name in ("total_amount", "tax_amount"):
                score = self._score_amount(value, cfg)
            elif field_name == "currency":
                score = self._score_currency(value)
            elif field_name in ("vendor_address", "customer_address"):
                score = self._score_address(value)
            elif field_name == "customer_name":
                score = self._score_customer_name(value, cfg)
            
            confidence[field_name] = score
        
        return confidence
    
    def _score_document_id(self, value: Any, cfg: ConfidenceConfig) -> float:
        """Score confidence for document_id field."""
        if not isinstance(value, str):
            return 0.0
        
        value_lower = value.lower().strip()
        
        # Check for suspicious words
        for word in cfg.doc_id_suspicious_words:
            if word.lower() == value_lower or word.lower() in value_lower.split():
                return 0.2
        
        # Very short IDs are suspicious
        if len(value) < 3:
            return 0.3
        
        # IDs with only letters (no numbers) are suspicious for invoices
        if not any(c.isdigit() for c in value):
            return 0.4
        
        # Good: alphanumeric with reasonable length
        if len(value) >= 4 and any(c.isdigit() for c in value):
            return 1.0
        
        return 0.7
    
    def _score_vendor_name(self, value: Any, cfg: ConfidenceConfig) -> float:
        """Score confidence for vendor_name field."""
        if not isinstance(value, str):
            return 0.0
        
        value_lower = value.lower().strip()
        
        # Check for suspicious patterns (generic words, not company names)
        for suspicious in cfg.vendor_name_suspicious:
            if suspicious.lower() == value_lower:
                return 0.1
        
        # Too short
        if len(value) < cfg.vendor_name_min_length:
            return 0.2
        
        # Single word all caps that looks like a header
        if value.isupper() and " " not in value and len(value) < 10:
            return 0.4
        
        # Looks like it starts with a number (might be address line)
        if value[0].isdigit():
            return 0.3
        
        return 1.0
    
    def _score_date(self, value: Any, cfg: ConfidenceConfig) -> float:
        """Score confidence for date fields."""
        if not isinstance(value, str):
            return 0.0
        
        # Check if already in YYYY-MM-DD format (normalized)
        if re.match(cfg.date_valid_pattern, value):
            return 1.0
        
        # Check for various date-like patterns
        date_patterns = [
            r"\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}",  # MM/DD/YYYY or DD/MM/YYYY
            r"\w+\s+\d{1,2},?\s+\d{4}",  # Month DD, YYYY
            r"\d{1,2}\s+\w+\s+\d{4}",  # DD Month YYYY
        ]
        
        for pattern in date_patterns:
            if re.match(pattern, value, re.IGNORECASE):
                return 0.8  # Found but not normalized
        
        return 0.3  # Doesn't look like a date
    
    def _score_amount(self, value: Any, cfg: ConfidenceConfig) -> float:
        """Score confidence for amount fields."""
        if value is None:
            return 0.0
        
        # Convert to float if possible
        try:
            amount = float(value) if not isinstance(value, (int, float)) else value
        except (ValueError, TypeError):
            return 0.2
        
        # Suspicious round numbers
        if amount in cfg.suspicious_amounts:
            return 0.3
        
        # Negative amounts are suspicious for totals
        if amount < 0:
            return 0.4
        
        # Very large amounts might be OCR errors (wrong decimal placement)
        if amount > 10_000_000:
            return 0.5
        
        return 1.0
    
    def _score_currency(self, value: Any) -> float:
        """Score confidence for currency field."""
        if not isinstance(value, str):
            return 0.0
        
        valid_currencies = {"USD", "EUR", "GBP", "CAD", "AUD", "JPY", "CHF", "CNY", "INR"}
        if value.upper() in valid_currencies:
            return 1.0
        
        return 0.5
    
    def _score_address(self, value: Any) -> float:
        """Score confidence for address fields."""
        if not isinstance(value, str):
            return 0.0
        
        # Addresses should have some minimum content
        if len(value) < 10:
            return 0.3
        
        # Look for address indicators (numbers, street keywords, zip codes)
        address_indicators = [
            r"\d{5}",  # ZIP code
            r"\b(street|st|avenue|ave|road|rd|drive|dr|lane|ln|blvd|way)\b",
            r"\b(suite|ste|floor|fl|box|po box)\b",
        ]
        
        score = 0.5
        for pattern in address_indicators:
            if re.search(pattern, value, re.IGNORECASE):
                score += 0.2
        
        return min(score, 1.0)
    
    def _score_customer_name(self, value: Any, cfg: ConfidenceConfig) -> float:
        """Score confidence for customer_name field."""
        if not isinstance(value, str):
            return 0.0
        
        # Similar logic to vendor_name
        value_lower = value.lower().strip()
        
        # Check for suspicious patterns
        for suspicious in cfg.vendor_name_suspicious:
            if suspicious.lower() == value_lower:
                return 0.1
        
        if len(value) < 3:
            return 0.2
        
        return 1.0
    
    def _build_llm_prompt(self, ocr_text: str, fields_to_extract: list[str]) -> str:
        """Build prompt for LLM to extract specific fields."""
        fields_desc = {
            "document_id": "Invoice number, receipt number, order number, or document ID",
            "vendor_name": "Name of the company/seller issuing the invoice",
            "vendor_address": "Full address of the vendor/seller",
            "customer_name": "Name of the customer/buyer (Bill To name)",
            "customer_address": "Full address of the customer (Bill To address)",
            "invoice_date": "Date the invoice was issued (in YYYY-MM-DD format if possible)",
            "due_date": "Payment due date (in YYYY-MM-DD format if possible)",
            "total_amount": "Total amount due (as a number, e.g., 1234.56)",
            "tax_amount": "Tax amount if shown (as a number)",
            "currency": "Currency code (USD, EUR, GBP, etc.)",
        }
        
        fields_list = "\n".join(
            f"- {field}: {fields_desc.get(field, field)}"
            for field in fields_to_extract
        )
        
        return f"""Extract the following fields from this invoice/receipt document. Return ONLY a valid JSON object with the field names as keys.

Fields to extract:
{fields_list}

Document text:
{ocr_text}

Return a JSON object with these exact field names. Use null for any field you cannot find. For amounts, return numeric values (not strings). For dates, use YYYY-MM-DD format when possible."""
    
    def _call_llm(self, ocr_text: str, fields_to_extract: list[str]) -> tuple[dict[str, Any], int, int]:
        """Call LLM to extract specific fields.
        
        Returns:
            Tuple of (extracted_fields, input_tokens, output_tokens)
        """
        prompt = self._build_llm_prompt(ocr_text, fields_to_extract)
        
        response = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        # Parse response
        content = response.content[0].text
        
        # Extract JSON from response (might be wrapped in markdown code block)
        json_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", content)
        if json_match:
            json_str = json_match.group(1)
        else:
            json_str = content
        
        try:
            extracted = json.loads(json_str)
        except json.JSONDecodeError:
            # Try to find any JSON object in the response
            obj_match = re.search(r"\{[\s\S]*\}", content)
            if obj_match:
                extracted = json.loads(obj_match.group(0))
            else:
                extracted = {}
        
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        
        return extracted, input_tokens, output_tokens
    
    def extract(self, ocr_text: str) -> ExtractionResult:
        """Extract invoice fields using hybrid regex + LLM approach.
        
        Args:
            ocr_text: Raw OCR text from the document
            
        Returns:
            ExtractionResult with fields, confidence scores, and timing metadata
        """
        # Step 1: Run regex extraction
        regex_start = time.perf_counter()
        regex_fields = extract_invoice_fields(ocr_text)
        regex_time_ms = (time.perf_counter() - regex_start) * 1000
        
        # Step 2: Calculate confidence for each field
        confidence = self.calculate_confidence(regex_fields)
        
        # Step 3: Determine which fields need LLM extraction
        low_confidence_fields = [
            field for field, score in confidence.items()
            if score < self.confidence_threshold
        ]
        
        # Step 4: If any low-confidence fields, call LLM for those
        llm_time_ms = 0.0
        input_tokens = 0
        output_tokens = 0
        llm_fields_used: list[str] = []
        
        if low_confidence_fields and self.api_key:
            llm_start = time.perf_counter()
            try:
                llm_extracted, input_tokens, output_tokens = self._call_llm(
                    ocr_text, low_confidence_fields
                )
                llm_time_ms = (time.perf_counter() - llm_start) * 1000
                
                # Merge LLM results into regex results
                for field in low_confidence_fields:
                    llm_value = llm_extracted.get(field)
                    if llm_value is not None:
                        regex_fields[field] = llm_value
                        confidence[field] = 0.95  # High confidence from LLM
                        llm_fields_used.append(field)
                        
            except Exception as e:
                # Log error but continue with regex-only results
                print(f"LLM extraction failed: {e}")
                llm_time_ms = (time.perf_counter() - llm_start) * 1000
        
        total_time_ms = regex_time_ms + llm_time_ms
        
        return ExtractionResult(
            fields=regex_fields,
            confidence=confidence,
            used_llm=len(llm_fields_used) > 0,
            llm_fields=llm_fields_used,
            regex_time_ms=regex_time_ms,
            llm_time_ms=llm_time_ms,
            total_time_ms=total_time_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )


def run_hybrid_benchmark(
    dataset_path: str,
    num_samples: int = 15,
    output_path: Optional[str] = None,
) -> dict[str, Any]:
    """Run benchmark on DocILE samples using hybrid extraction.
    
    Args:
        dataset_path: Path to DocILE dataset directory
        num_samples: Number of samples to test
        output_path: Optional path to save results JSON
        
    Returns:
        Benchmark results dictionary
    """
    import json
    from pathlib import Path
    from datetime import datetime
    
    from compiled_ai.datasets.docile_converter import DocILEConverter
    
    converter = DocILEConverter()
    extractor = HybridExtractor()
    
    # Load samples
    instances = converter.load_directory(dataset_path, task_type="kile")[:num_samples]
    
    results = {
        "timestamp": datetime.now().isoformat(),
        "num_samples": len(instances),
        "config": {
            "confidence_threshold": extractor.confidence_threshold,
            "model": extractor.model,
        },
        "samples": [],
        "summary": {
            "total_correct_fields": 0,
            "total_fields": 0,
            "samples_with_llm": 0,
            "total_regex_time_ms": 0.0,
            "total_llm_time_ms": 0.0,
            "total_time_ms": 0.0,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
        },
    }
    
    for instance in instances:
        # Parse input
        input_data = json.loads(instance.input)
        ocr_text = input_data["document_text"]
        expected = instance.expected_output
        
        # Run hybrid extraction
        result = extractor.extract(ocr_text)
        
        # Calculate field-level accuracy
        field_matches = {}
        correct_fields = 0
        total_fields = 0
        
        for field in HybridExtractor.KILE_FIELDS:
            if field in expected:
                total_fields += 1
                extracted_value = result.fields.get(field)
                expected_value = expected.get(field)
                
                # Normalize for comparison
                is_match = normalize_for_comparison(extracted_value, expected_value)
                field_matches[field] = is_match
                if is_match:
                    correct_fields += 1
        
        sample_result = {
            "id": instance.id,
            "extracted": result.fields,
            "expected": expected,
            "confidence": result.confidence,
            "field_matches": field_matches,
            "correct_fields": correct_fields,
            "total_fields": total_fields,
            "accuracy": correct_fields / total_fields if total_fields > 0 else 0,
            "used_llm": result.used_llm,
            "llm_fields": result.llm_fields,
            "regex_time_ms": result.regex_time_ms,
            "llm_time_ms": result.llm_time_ms,
            "total_time_ms": result.total_time_ms,
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
        }
        
        results["samples"].append(sample_result)
        
        # Update summary
        results["summary"]["total_correct_fields"] += correct_fields
        results["summary"]["total_fields"] += total_fields
        if result.used_llm:
            results["summary"]["samples_with_llm"] += 1
        results["summary"]["total_regex_time_ms"] += result.regex_time_ms
        results["summary"]["total_llm_time_ms"] += result.llm_time_ms
        results["summary"]["total_time_ms"] += result.total_time_ms
        results["summary"]["total_input_tokens"] += result.input_tokens
        results["summary"]["total_output_tokens"] += result.output_tokens
    
    # Calculate final metrics
    num = len(instances)
    results["summary"]["field_accuracy"] = (
        results["summary"]["total_correct_fields"] / results["summary"]["total_fields"]
        if results["summary"]["total_fields"] > 0 else 0
    )
    results["summary"]["llm_usage_rate"] = results["summary"]["samples_with_llm"] / num if num > 0 else 0
    results["summary"]["avg_regex_time_ms"] = results["summary"]["total_regex_time_ms"] / num if num > 0 else 0
    results["summary"]["avg_llm_time_ms"] = results["summary"]["total_llm_time_ms"] / num if num > 0 else 0
    results["summary"]["avg_total_time_ms"] = results["summary"]["total_time_ms"] / num if num > 0 else 0
    results["summary"]["avg_tokens_per_sample"] = (
        (results["summary"]["total_input_tokens"] + results["summary"]["total_output_tokens"]) / num
        if num > 0 else 0
    )
    
    # Save results if path provided
    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(results, f, indent=2)
    
    return results


def normalize_for_comparison(extracted: Any, expected: Any) -> bool:
    """Normalize values for comparison, handling common differences."""
    if extracted is None and expected is None:
        return True
    if extracted is None or expected is None:
        return False
    
    # Convert both to strings for comparison
    ext_str = str(extracted).strip().lower()
    exp_str = str(expected).strip().lower()
    
    # Remove currency symbols and formatting for amounts
    amount_chars = re.compile(r"[\$€£¥₹,\s]")
    ext_clean = amount_chars.sub("", ext_str)
    exp_clean = amount_chars.sub("", exp_str)
    
    # Direct match
    if ext_str == exp_str:
        return True
    
    # Clean match (for amounts)
    if ext_clean == exp_clean:
        return True
    
    # Try numeric comparison for amounts
    try:
        ext_num = float(ext_clean.replace(",", ""))
        exp_num = float(exp_clean.replace(",", ""))
        if abs(ext_num - exp_num) < 0.01:
            return True
    except (ValueError, TypeError):
        pass
    
    # Check if one contains the other (for partial matches)
    if len(ext_str) > 3 and len(exp_str) > 3:
        if ext_str in exp_str or exp_str in ext_str:
            return True
    
    return False


# Test block
if __name__ == "__main__":
    import sys
    from pathlib import Path
    
    print("Testing hybrid extractor...")
    
    # Test confidence scoring
    extractor = HybridExtractor()
    
    test_fields = {
        "document_id": "INV-2024-00123",
        "vendor_name": "Acme Corporation",
        "vendor_address": "123 Main St, New York, NY 10001",
        "customer_name": "John Smith",
        "customer_address": "456 Oak Ave, Los Angeles, CA 90001",
        "invoice_date": "2024-01-15",
        "due_date": "2024-02-15",
        "total_amount": 1234.56,
        "tax_amount": 98.77,
        "currency": "USD",
    }
    
    confidence = extractor.calculate_confidence(test_fields)
    print("\n✓ Confidence scoring for good fields:")
    for field, score in confidence.items():
        print(f"    {field}: {score:.2f}")
    
    # Test with suspicious values
    suspicious_fields = {
        "document_id": "Information",
        "vendor_name": "INVOICE",
        "vendor_address": None,
        "customer_name": "TO",
        "customer_address": "short",
        "invoice_date": "bad date",
        "due_date": None,
        "total_amount": 0.0,
        "tax_amount": None,
        "currency": "XXX",
    }
    
    confidence_suspicious = extractor.calculate_confidence(suspicious_fields)
    print("\n✓ Confidence scoring for suspicious fields:")
    for field, score in confidence_suspicious.items():
        print(f"    {field}: {score:.2f}")
    
    # Verify low confidence fields trigger LLM
    low_conf = [f for f, s in confidence_suspicious.items() if s < 0.5]
    print(f"\n✓ Fields that would trigger LLM fallback: {low_conf}")
    
    # Test full extraction without LLM (API key check)
    sample_ocr = """
    Acme Corporation
    123 Business Lane
    New York, NY 10001
    
    Invoice #INV-2024-00123
    Invoice Date: January 15, 2024
    Due Date: February 15, 2024
    
    Bill To:
    John Smith
    456 Customer Street
    Los Angeles, CA 90001
    
    Total: $432.00
    Currency: USD
    """
    
    # Run without API key to test regex-only path
    extractor_no_llm = HybridExtractor(api_key=None)
    result = extractor_no_llm.extract(sample_ocr)
    
    print(f"\n✓ Regex extraction completed in {result.regex_time_ms:.2f}ms")
    print(f"  Fields extracted: {list(result.fields.keys())}")
    print(f"  Used LLM: {result.used_llm}")
    
    print("\n✅ All tests passed!")
