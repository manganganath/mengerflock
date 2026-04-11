#!/usr/bin/env python3
"""
First Fit Decreasing (FFD) bin packing solver.

Input format (one item per line after header):
  Line 1: number of items
  Line 2: bin capacity
  Lines 3+: item weights (one per line)

Output: number of bins used
"""
import sys


def first_fit_decreasing(items: list[int], capacity: int) -> int:
    """Pack items into bins using First Fit Decreasing. Returns bin count."""
    items_sorted = sorted(items, reverse=True)
    bins: list[int] = []  # remaining capacity in each bin

    for item in items_sorted:
        placed = False
        for i, remaining in enumerate(bins):
            if remaining >= item:
                bins[i] -= item
                placed = True
                break
        if not placed:
            bins.append(capacity - item)

    return len(bins)


def main():
    if len(sys.argv) < 2:
        print("Usage: python solver.py <instance_file>", file=sys.stderr)
        sys.exit(1)

    instance_path = sys.argv[1]

    with open(instance_path) as f:
        lines = [line.strip() for line in f if line.strip()]

    n_items = int(lines[0])
    capacity = int(lines[1])
    items = [int(lines[i + 2]) for i in range(n_items)]

    result = first_fit_decreasing(items, capacity)
    print(result)


if __name__ == "__main__":
    main()
