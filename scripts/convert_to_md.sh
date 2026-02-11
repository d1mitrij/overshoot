#!/usr/bin/env bash
#
# convert_to_md.sh — Convert PDF and EPUB files to Markdown
#
# Usage: ./scripts/convert_to_md.sh [directory]
#   directory  Path containing PDF/EPUB files (default: references/)
#
# Tools used:
#   PDF  → marker_single (high-quality PDF-to-Markdown)
#   EPUB → pandoc

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DIR="${1:-$PROJECT_ROOT/references}"
OUTPUT_DIR="$DIR/md_output"

mkdir -p "$OUTPUT_DIR"

converted=0
failed=0

# --- Convert PDFs with marker_single ---
for pdf in "$DIR"/*.pdf "$DIR"/*.PDF; do
    [ -f "$pdf" ] || continue
    basename="$(basename "$pdf")"
    stem="${basename%.*}"
    echo "Converting PDF: $basename"
    if marker_single "$pdf" --output_dir "$OUTPUT_DIR" --output_format markdown --disable_image_extraction 2>&1; then
        echo "  -> Done: $stem"
        ((converted++))
    else
        echo "  -> FAILED: $basename" >&2
        ((failed++))
    fi
done

# --- Convert EPUBs with pandoc ---
for epub in "$DIR"/*.epub "$DIR"/*.EPUB; do
    [ -f "$epub" ] || continue
    basename="$(basename "$epub")"
    stem="${basename%.*}"
    outfile="$OUTPUT_DIR/${stem}.md"
    echo "Converting EPUB: $basename"
    if pandoc "$epub" -t markdown -o "$outfile" --wrap=none 2>&1; then
        echo "  -> Done: $outfile"
        ((converted++))
    else
        echo "  -> FAILED: $basename" >&2
        ((failed++))
    fi
done

echo ""
echo "=== Conversion complete ==="
echo "Converted: $converted"
echo "Failed:    $failed"
echo "Output:    $OUTPUT_DIR"
