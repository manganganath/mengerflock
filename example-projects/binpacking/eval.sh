#!/usr/bin/env bash
# MengerFlock benchmark evaluation script for bin packing
# Usage: ./eval.sh <solver_command> <instance_file> <seed> <timeout>
# Output: number of bins used on stdout, or "FAIL" on error
# Note: seed is accepted but unused (FFD is deterministic)

set -euo pipefail

SOLVER="$1"
INSTANCE="$2"
SEED="${3:-42}"
TIMEOUT="${4:-30}"

if [ ! -f "$INSTANCE" ]; then
    echo "FAIL: instance not found: $INSTANCE" >&2
    exit 1
fi

# macOS-compatible timeout using perl
_timeout() {
    local secs="$1"; shift
    perl -e 'alarm shift; exec @ARGV' "$secs" "$@"
}

RESULT=$(_timeout "$TIMEOUT" $SOLVER "$INSTANCE" 2>/dev/null)

if [ -n "$RESULT" ] && [ "$RESULT" != "FAIL" ]; then
    echo "$RESULT"
else
    echo "FAIL: solver returned no result" >&2
    exit 1
fi
