#!/bin/bash
# Download DocILE (Document Information Localization and Extraction) dataset.
#
# IMPORTANT: Requires an access token from https://docile.rossum.ai/
#
# Usage:
#   ./scripts/download_docile.sh TOKEN
#   ./scripts/download_docile.sh TOKEN datasets/docile

set -e

TOKEN="$1"
OUTPUT_DIR="${2:-datasets/docile}"

if [ -z "$TOKEN" ]; then
    echo "DocILE Dataset Downloader"
    echo "========================="
    echo ""
    echo "Usage: $0 TOKEN [OUTPUT_DIR]"
    echo ""
    echo "Arguments:"
    echo "  TOKEN       Access token from docile.rossum.ai (required)"
    echo "  OUTPUT_DIR  Output directory (default: datasets/docile)"
    echo ""
    echo "To get your token:"
    echo "  1. Visit https://docile.rossum.ai/"
    echo "  2. Complete the Dataset Access Request form"
    echo "  3. Receive your token via email"
    echo ""
    echo "Dataset Information:"
    echo "  - 6,680 annotated business documents"
    echo "  - 100,000 synthetic documents"
    echo "  - 55 semantic field types"
    echo "  - Tasks: KILE (key info extraction), LIR (line item recognition)"
    exit 1
fi

echo "DocILE Dataset Downloader"
echo "========================="
echo ""
echo "Output directory: $OUTPUT_DIR"
echo ""

mkdir -p "$OUTPUT_DIR"

# Download annotated train/val (main dataset)
echo "[1/2] Downloading annotated-trainval (6,680 documents)..."
curl -L --progress-bar \
    "https://docile.rossum.ai/download/annotated-trainval?token=$TOKEN" \
    -o "$OUTPUT_DIR/annotated-trainval.zip"

if [ -f "$OUTPUT_DIR/annotated-trainval.zip" ]; then
    echo "      Extracting..."
    unzip -q "$OUTPUT_DIR/annotated-trainval.zip" -d "$OUTPUT_DIR"
    rm "$OUTPUT_DIR/annotated-trainval.zip"
    echo "      Done."
else
    echo "      Error: Download failed. Check your token."
    exit 1
fi

# Download test set
echo "[2/2] Downloading test set..."
curl -L --progress-bar \
    "https://docile.rossum.ai/download/test?token=$TOKEN" \
    -o "$OUTPUT_DIR/test.zip"

if [ -f "$OUTPUT_DIR/test.zip" ]; then
    echo "      Extracting..."
    unzip -q "$OUTPUT_DIR/test.zip" -d "$OUTPUT_DIR"
    rm "$OUTPUT_DIR/test.zip"
    echo "      Done."
else
    echo "      Warning: Test set download failed (may require competition registration)."
fi

echo ""
echo "Download complete!"
echo ""
echo "Dataset structure:"
echo "  $OUTPUT_DIR/"
echo "  ├── annotated-trainval/"
echo "  │   └── [document_id]/"
echo "  │       ├── annotation.json  (field annotations)"
echo "  │       ├── ocr.json         (OCR results)"
echo "  │       └── document.pdf     (original PDF)"
echo "  └── test/"
echo ""
echo "Usage example:"
echo "  from compiled_ai.runner import DatasetLoader"
echo "  loader = DatasetLoader('datasets')"
echo "  docile = loader.load_external('docile', '$OUTPUT_DIR', task_type='kile')"
