#!/bin/bash
# Build the Compiled AI paper from LaTeX to PDF
#
# Usage:
#   ./scripts/build_paper.sh          # Build the paper
#   ./scripts/build_paper.sh clean    # Clean auxiliary files
#   ./scripts/build_paper.sh watch    # Watch for changes and rebuild

set -e

PAPER_DIR="paper"
TEX_FILE="compiled_ai_arxiv_paper_v2.tex"
PDF_FILE="compiled_ai_arxiv_paper_v2.pdf"

cd "$(dirname "$0")/.."

# Check if pdflatex is available
if ! command -v pdflatex &> /dev/null; then
    echo "Error: pdflatex not found. Please install a LaTeX distribution."
    echo "  macOS: brew install --cask mactex"
    echo "  Ubuntu: sudo apt-get install texlive-full"
    exit 1
fi

clean() {
    echo "Cleaning auxiliary files..."
    cd "$PAPER_DIR"
    rm -f *.aux *.log *.out *.toc *.lof *.lot *.bbl *.blg *.synctex.gz *.fdb_latexmk *.fls
    echo "Done."
}

build() {
    echo "Building paper..."
    cd "$PAPER_DIR"

    # Run pdflatex twice for references and TOC
    echo "First pass..."
    pdflatex -interaction=nonstopmode "$TEX_FILE"

    # Run bibtex if .bib file exists
    if ls *.bib 1> /dev/null 2>&1; then
        echo "Running bibtex..."
        bibtex "${TEX_FILE%.tex}" || true
    fi

    echo "Second pass..."
    pdflatex -interaction=nonstopmode "$TEX_FILE"

    # Third pass for cross-references
    echo "Third pass..."
    pdflatex -interaction=nonstopmode "$TEX_FILE"

    echo ""
    echo "Build complete: $PAPER_DIR/$PDF_FILE"
}

watch() {
    echo "Watching for changes in $PAPER_DIR/$TEX_FILE..."
    echo "Press Ctrl+C to stop."

    if command -v fswatch &> /dev/null; then
        fswatch -o "$PAPER_DIR/$TEX_FILE" | while read; do
            echo ""
            echo "Change detected, rebuilding..."
            build
        done
    elif command -v inotifywait &> /dev/null; then
        while true; do
            inotifywait -q -e modify "$PAPER_DIR/$TEX_FILE"
            echo ""
            echo "Change detected, rebuilding..."
            build
        done
    else
        echo "Error: Neither fswatch nor inotifywait found."
        echo "  macOS: brew install fswatch"
        echo "  Linux: sudo apt-get install inotify-tools"
        exit 1
    fi
}

case "${1:-build}" in
    build)
        build
        ;;
    clean)
        clean
        ;;
    watch)
        watch
        ;;
    *)
        echo "Usage: $0 {build|clean|watch}"
        exit 1
        ;;
esac
