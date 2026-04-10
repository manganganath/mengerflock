#!/usr/bin/env bash
# AlgoForge benchmark evaluation script
# Usage: ./eval.sh <binary> <instance.tsp> <seed> <timeout>
# Output: tour_length on stdout, or "FAIL" on error

set -euo pipefail

BINARY="$1"
INSTANCE="$2"
SEED="${3:-42}"
TIMEOUT="${4:-30}"

if [ ! -x "$BINARY" ]; then
    echo "FAIL: binary not found or not executable: $BINARY" >&2
    exit 1
fi

if [ ! -f "$INSTANCE" ]; then
    echo "FAIL: instance not found: $INSTANCE" >&2
    exit 1
fi

# Create a temporary parameter file for LKH
PARAM_FILE=$(mktemp /tmp/algoforge_eval_XXXXXX.par)
TOUR_FILE=$(mktemp /tmp/algoforge_eval_XXXXXX.tour)

cat > "$PARAM_FILE" <<EOF
PROBLEM_FILE = $INSTANCE
TOUR_FILE = $TOUR_FILE
SEED = $SEED
RUNS = 1
EOF

# Run with timeout
if timeout "$TIMEOUT" "$BINARY" "$PARAM_FILE" > /dev/null 2>&1; then
    # Extract tour length from tour file
    if [ -f "$TOUR_FILE" ]; then
        TOUR_LENGTH=$(grep -oP '(?<=COMMENT : Length = )\d+' "$TOUR_FILE" || echo "FAIL")
        echo "$TOUR_LENGTH"
    else
        echo "FAIL: no tour file produced" >&2
        exit 1
    fi
else
    echo "FAIL: timeout or crash" >&2
    exit 1
fi

# Cleanup
rm -f "$PARAM_FILE" "$TOUR_FILE"
