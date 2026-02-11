#!/usr/bin/env bash
#
# setup.sh — Bootstrap the Ecological Overshoot Calculator
#
# After cloning the repo, run this script to:
#   1. Install Python dependencies
#   2. Download all FAOSTAT bulk data (~400 MB)
#   3. Extract and prepare CSV datasets
#
# Usage:
#   ./setup.sh                  # full setup (includes ~265 MB trade data)
#   ./setup.sh --skip-trade     # skip the large trade dataset
#   ./setup.sh --quick          # skip trade + food balance sheets

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================"
echo "  Ecological Overshoot Calculator Setup"
echo "========================================"
echo ""

# ── 1. Python dependencies ────────────────────────────────────────────────
echo "Step 1: Checking Python dependencies..."

if ! command -v python3 &>/dev/null; then
    echo "ERROR: python3 not found. Please install Python 3.8+."
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "  Python version: $PYTHON_VERSION"

# Install from requirements.txt
if [ -f requirements.txt ]; then
    echo "  Installing packages from requirements.txt..."
    pip3 install --quiet -r requirements.txt
else
    echo "  Installing core packages..."
    pip3 install --quiet pandas numpy requests
fi
echo "  Done."
echo ""

# ── 2. Create data directories ───────────────────────────────────────────
echo "Step 2: Creating data directory structure..."
mkdir -p data/raw
mkdir -p data/{01_cropland,02_grazing,03_forest,04_fishing}
mkdir -p data/{05_built_up,06_carbon,07_population,08_trade}
mkdir -p data/{09_factors,10_reference_parameters}
echo "  Done."
echo ""

# ── 3. Fetch all data ────────────────────────────────────────────────────
echo "Step 3: Downloading FAOSTAT data and reference parameters..."
echo "  (This downloads ~400 MB from FAO servers — may take several minutes)"
echo ""

FETCH_ARGS=""
for arg in "$@"; do
    case "$arg" in
        --skip-trade)
            FETCH_ARGS="$FETCH_ARGS --skip-trade"
            echo "  [skipping trade data — saves ~265 MB]"
            ;;
        --quick)
            FETCH_ARGS="$FETCH_ARGS --skip-trade --skip-food-balance"
            echo "  [quick mode — skipping trade + food balance sheets]"
            ;;
    esac
done

python3 scripts/fetch_footprint_data.py $FETCH_ARGS

echo ""
echo "========================================"
echo "  Setup complete!"
echo ""
echo "  Next steps:"
echo "    python3 scripts/calculate_overshoot.py"
echo ""
echo "  Output files will be written to:"
echo "    data/overshoot_results.csv"
echo "    data/overshoot_global_summary.csv"
echo "========================================"
