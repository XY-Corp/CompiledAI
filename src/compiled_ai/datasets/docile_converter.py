"""DocILE converter - converts DocILE format to generic DatasetInstance.

DocILE focuses on document information extraction:
- KILE: key information extraction (header fields)
- LIR: line item recognition (table line items)

This converter keeps ALL DocILE-specific parsing logic here so that
baselines remain dataset-agnostic and only see normalized inputs.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from .base import DatasetConverter, DatasetInstance


TaskType = Literal["kile", "lir"]


class DocILEConverter(DatasetConverter):
    """Converts DocILE invoices/receipts to generic DatasetInstance."""

    # DocILE field types for KILE task
    KILE_FIELDS = [
        "document_id",
        "vendor_name",
        "vendor_address",
        "customer_name",
        "customer_address",
        "invoice_id",
        "invoice_date",
        "due_date",
        "total_amount",
        "tax_amount",
        "currency",
    ]

    # Mapping from DocILE field names to standard KILE field names
    DOCILE_TO_KILE_FIELD_MAP: dict[str, str] = {
        # Document ID
        "document_id": "document_id",
        # Vendor fields
        "vendor_name": "vendor_name",
        "vendor_address": "vendor_address",
        # Customer fields (DocILE uses billing/shipping variants)
        "customer_name": "customer_name",
        "customer_billing_name": "customer_name",
        "customer_shipping_name": "customer_name",
        "customer_address": "customer_address",
        "customer_billing_address": "customer_address",
        "customer_shipping_address": "customer_address",
        # Invoice fields
        "invoice_id": "invoice_id",
        "invoice_number": "invoice_id",
        "date_issue": "invoice_date",
        "invoice_date": "invoice_date",
        "date_due": "due_date",
        "due_date": "due_date",
        # Amount fields
        "amount_total_gross": "total_amount",
        "total_amount": "total_amount",
        "amount_due": "total_amount",  # Often same as total
        "tax_amount": "tax_amount",
        "tax": "tax_amount",
        # Currency
        "currency": "currency",
        "currency_code": "currency",
        "currency_code_amount_due": "currency",
    }

    def convert(self, raw_data: dict) -> list[DatasetInstance]:
        """Convert a single DocILE document to DatasetInstance.

        Expects raw_data of the form:
            {
                "id": <doc_id>,
                "annotation": {...},
                "ocr_text": "...",
                "task_type": "kile" | "lir",
            }
        """
        doc_id = raw_data["id"]
        annotation = raw_data["annotation"]
        ocr_text = raw_data.get("ocr_text", "")
        task_type: TaskType = raw_data.get("task_type", "kile")  # type: ignore[assignment]

        if task_type == "kile":
            expected = self._extract_kile_fields(annotation)
            output_format = self._build_kile_output_format()
        else:
            expected = self._extract_line_items(annotation)
            output_format = self._build_lir_output_format()

        # The input to baselines is the document text plus task_type
        # Baselines remain unaware of DocILE specifics.
        raw_input = json.dumps(
            {
                "document_text": ocr_text,
                "task_type": task_type,
            }
        )

        instance = DatasetInstance(
            id=f"{doc_id}_{task_type}",
            input=raw_input,
            output_format=output_format,
            expected_output=expected,
            context={
                "task_type": task_type,
            },
        )

        return [instance]

    # ------------------------------------------------------------------
    # Loading helpers
    # ------------------------------------------------------------------

    def load_file(self, path: str) -> list[DatasetInstance]:
        """Load a single DocILE document by annotation file path.

        Args:
            path: Path to annotation JSON file

        Returns:
            List of DatasetInstance (one per task type)
        """
        import json
        from pathlib import Path

        ann_path = Path(path)
        doc_id = ann_path.stem

        # Find OCR file in sibling directory
        base_dir = ann_path.parent.parent
        ocr_path = base_dir / "ocr" / f"{doc_id}.json"

        with open(ann_path) as f:
            annotation = json.load(f)

        ocr_text = ""
        if ocr_path.exists():
            with open(ocr_path) as f:
                ocr_data = json.load(f)
            ocr_text = self._extract_ocr_text(ocr_data)

        return self.convert({
            "id": doc_id,
            "annotation": annotation,
            "ocr_text": ocr_text,
            "task_type": "kile",  # Default to KILE
        })

    def load_directory(
        self,
        dir_path: str,
        task_type: TaskType = "kile",
        split: str | None = None,
    ) -> list[DatasetInstance]:
        """Load DocILE dataset directory and convert to DatasetInstance list.

        Directory layout (flat):
            annotations/<doc_id>.json
            ocr/<doc_id>.json
            pdfs/<doc_id>.pdf
            train.json / val.json / test.json (lists of doc_ids)
        """
        base = Path(dir_path)
        doc_ids = self._find_document_ids(base, split)

        instances: list[DatasetInstance] = []

        for doc_id in doc_ids:
            annotation_file = base / "annotations" / f"{doc_id}.json"
            ocr_file = base / "ocr" / f"{doc_id}.json"

            if not annotation_file.exists():
                continue

            with open(annotation_file) as f:
                annotation = json.load(f)

            ocr_text = ""
            if ocr_file.exists():
                with open(ocr_file) as f:
                    ocr_data = json.load(f)
                ocr_text = self._extract_ocr_text(ocr_data)

            instances.extend(
                self.convert(
                    {
                        "id": doc_id,
                        "annotation": annotation,
                        "ocr_text": ocr_text,
                        "task_type": task_type,
                    }
                )
            )

        return instances

    # ------------------------------------------------------------------
    # Internal extraction helpers (ported from DocILEAdapter)
    # ------------------------------------------------------------------

    def _find_document_ids(self, path: Path, split: str | None) -> list[str]:
        """Find document IDs in DocILE structure."""
        doc_ids: list[str] = []

        # Check for split JSON files (train.json, val.json, test.json, trainval.json)
        if split == "train":
            split_file = path / "train.json"
        elif split == "val":
            split_file = path / "val.json"
        elif split == "test":
            split_file = path / "test.json"
        else:
            # Default: use trainval.json if available, otherwise scan all annotations
            split_file = path / "trainval.json"

        if split_file.exists():
            with open(split_file) as f:
                doc_ids = json.load(f)
                if not isinstance(doc_ids, list):
                    doc_ids = []
        else:
            # Fallback: scan annotations directory
            annotations_dir = path / "annotations"
            if annotations_dir.exists():
                for annotation_file in annotations_dir.glob("*.json"):
                    doc_id = annotation_file.stem
                    doc_ids.append(doc_id)

        return sorted(doc_ids)

    def _extract_ocr_text(self, ocr_data: dict) -> str:
        """Extract plain text from DocILE OCR JSON."""
        texts: list[str] = []

        # OCR structure: pages -> blocks -> lines -> words
        for page in ocr_data.get("pages", []):
            for block in page.get("blocks", []):
                for line in block.get("lines", []):
                    line_text_parts = [w.get("value", w.get("text", "")) for w in line.get("words", [])]
                    line_text = " ".join(t for t in line_text_parts if t)
                    if line_text:
                        texts.append(line_text)

        return "\n".join(texts)

    def _extract_kile_fields(self, annotation: dict) -> dict:
        """Extract key information fields from annotation and normalize to KILE field names."""
        raw_fields: dict[str, str] = {}
        field_extractions = annotation.get("field_extractions", [])

        if isinstance(field_extractions, list):
            for field in field_extractions:
                field_type = field.get("fieldtype", field.get("field_type", ""))
                value = field.get("text", field.get("value", ""))
                if field_type:
                    # Handle multiple values for same field type (take first or concatenate)
                    if field_type in raw_fields:
                        raw_fields[field_type] = f"{raw_fields[field_type]}\n{value}"
                    else:
                        raw_fields[field_type] = value

        # Normalize to KILE field names using mapping
        normalized: dict[str, str] = {}
        for docile_field, value in raw_fields.items():
            kile_field = self.DOCILE_TO_KILE_FIELD_MAP.get(docile_field)
            if kile_field:
                # If multiple docile fields map to same KILE field, prefer first non-empty
                if kile_field not in normalized:
                    normalized[kile_field] = value

        # Ensure we only include known KILE fields
        result = {field: normalized[field] for field in self.KILE_FIELDS if field in normalized}
        return result

    def _extract_line_items(self, annotation: dict) -> list[dict]:
        """Extract line items (LIR) from annotation."""
        items_by_id: dict[str, dict[str, Any]] = {}
        line_item_extractions = annotation.get("line_item_extractions", [])

        if isinstance(line_item_extractions, list):
            for item in line_item_extractions:
                line_id = str(item.get("line_item_id", ""))
                if not line_id:
                    # Some datasets may omit line_item_id; skip or group under a special key
                    continue

                entry = items_by_id.setdefault(
                    line_id,
                    {
                        "description": "",
                        "quantity": "",
                        "unit_price": "",
                        "amount": "",
                    },
                )

                field_type = item.get("fieldtype", item.get("field_type", ""))
                value = item.get("text", item.get("value", ""))

                if not field_type or not value:
                    continue

                field_type_lower = field_type.lower()
                if "description" in field_type_lower or field_type_lower in ("item", "name"):
                    entry["description"] = value
                elif "qty" in field_type_lower or "quantity" in field_type_lower:
                    entry["quantity"] = value
                elif "unit_price" in field_type_lower or "unit price" in field_type_lower or "price" in field_type_lower:
                    entry["unit_price"] = value
                elif "amount" in field_type_lower or "total" in field_type_lower:
                    entry["amount"] = value

        # Convert to list of line items, sorted by ID for determinism
        line_items: list[dict[str, Any]] = []
        for item_id in sorted(items_by_id.keys()):
            item = items_by_id[item_id]
            # Only keep line items that have at least a description or amount
            if any(item.values()):
                line_items.append(item)

        return line_items

    def _build_kile_output_format(self) -> dict:
        """Build a simple output_format description for KILE."""
        return {
            "type": "object",
            "fields": {
                field: "string - extracted field"
                for field in self.KILE_FIELDS
            },
        }

    def _build_lir_output_format(self) -> dict:
        """Build a simple output_format description for LIR."""
        return {
            "type": "array",
            "items": {
                "type": "object",
                "fields": {
                    "description": "string",
                    "quantity": "string or number",
                    "unit_price": "string",
                    "amount": "string",
                },
            },
        }

