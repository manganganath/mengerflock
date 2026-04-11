#!/usr/bin/env bash
# AlgoForge benchmark evaluation script
# Usage: ./eval.sh <binary> <instance.tsp> <seed> <timeout>
# Output: tour_length on stdout, or "FAIL" on error
# Compatible with macOS and Linux

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

# Create temporary files (macOS-compatible mktemp)
PARAM_FILE=$(mktemp /tmp/algoforge_eval_XXXXXX)
TOUR_FILE=$(mktemp /tmp/algoforge_eval_tour_XXXXXX)

trap 'rm -f "$PARAM_FILE" "$TOUR_FILE"' EXIT

cat > "$PARAM_FILE" <<EOF
PROBLEM_FILE = $INSTANCE
TOUR_FILE = $TOUR_FILE
SEED = $SEED
RUNS = 1
EOF

# macOS-compatible timeout using perl
_timeout() {
    local secs="$1"; shift
    perl -e 'alarm shift; exec @ARGV' "$secs" "$@"
}

if _timeout "$TIMEOUT" "$BINARY" "$PARAM_FILE" > /dev/null 2>&1; then
    if [ -f "$TOUR_FILE" ]; then
        # Extract tour length (compatible grep, no GNU -oP)
        TOUR_LENGTH=$(grep 'COMMENT : Length = ' "$TOUR_FILE" | sed 's/.*Length = //' | tr -d '[:space:]')
        if [ -n "$TOUR_LENGTH" ]; then
            echo "$TOUR_LENGTH"
        else
            echo "FAIL: could not parse tour length" >&2
            exit 1
        fi
    else
        echo "FAIL: no tour file produced" >&2
        exit 1
    fi
else
    echo "FAIL: timeout or crash" >&2
    exit 1
fi
