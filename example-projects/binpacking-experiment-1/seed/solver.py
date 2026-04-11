#!/usr/bin/env python3
"""
Bin packing solver: multi-strategy with aggressive local search.

Input format (one item per line after header):
  Line 1: number of items
  Line 2: bin capacity
  Lines 3+: item weights (one per line)

Output: number of bins used
"""
import sys
import random
from itertools import combinations


def bfd_pack(items, capacity):
    """Best Fit Decreasing. Returns list of bins (each a list of items)."""
    items_sorted = sorted(items, reverse=True)
    bins = []
    rem = []
    for item in items_sorted:
        best_i = -1
        best_r = capacity + 1
        for i, r in enumerate(rem):
            if r >= item and r < best_r:
                best_r = r
                best_i = i
        if best_i >= 0:
            bins[best_i].append(item)
            rem[best_i] -= item
        else:
            bins.append([item])
            rem.append(capacity - item)
    return bins


def ffd_pack(items, capacity):
    """First Fit Decreasing. Returns list of bins."""
    items_sorted = sorted(items, reverse=True)
    bins = []
    rem = []
    for item in items_sorted:
        placed = False
        for i, r in enumerate(rem):
            if r >= item:
                bins[i].append(item)
                rem[i] -= item
                placed = True
                break
        if not placed:
            bins.append([item])
            rem.append(capacity - item)
    return bins


def try_fit_greedy(items, bins, rem, capacity, skip):
    """Best-fit items into bins, skipping indices in skip. Rolls back on fail."""
    sorted_items = sorted(items, reverse=True)
    changes = []
    for item in sorted_items:
        best_i = -1
        best_r = capacity + 1
        for i, r in enumerate(rem):
            if i in skip:
                continue
            if r >= item and r < best_r:
                best_r = r
                best_i = i
        if best_i < 0:
            for bi, it in reversed(changes):
                rem[bi] += it
                bins[bi].pop()
            return False
        bins[best_i].append(item)
        rem[best_i] -= item
        changes.append((best_i, item))
    return True


def bin_elimination(bins, capacity):
    rem = [capacity - sum(b) for b in bins]
    improved = True
    while improved:
        improved = False
        order = sorted(range(len(bins)), key=lambda i: sum(bins[i]))
        for idx in order:
            if not bins[idx]:
                continue
            items = list(bins[idx])
            old = bins[idx]
            bins[idx] = []
            rem[idx] = capacity
            if try_fit_greedy(items, bins, rem, capacity, {idx}):
                bins.pop(idx)
                rem.pop(idx)
                improved = True
                break
            else:
                bins[idx] = old
                rem[idx] = capacity - sum(old)
    return bins


def item_relocation(bins, capacity):
    rem = [capacity - sum(b) for b in bins]
    improved = True
    while improved:
        improved = False
        for src in range(len(bins)):
            if len(bins[src]) <= 1:
                continue
            found = False
            for item in sorted(bins[src]):
                for dst in range(len(bins)):
                    if dst == src or rem[dst] < item:
                        continue
                    bins[src].remove(item)
                    rem[src] += item
                    bins[dst].append(item)
                    rem[dst] -= item
                    src_items = list(bins[src])
                    old_src = list(bins[src])
                    bins[src] = []
                    rem[src] = capacity
                    if try_fit_greedy(src_items, bins, rem, capacity, {src}):
                        bins.pop(src)
                        rem.pop(src)
                        improved = True
                        found = True
                        break
                    else:
                        bins[src] = old_src
                        rem[src] = capacity - sum(old_src)
                        bins[dst].remove(item)
                        rem[dst] += item
                        bins[src].append(item)
                        rem[src] -= item
                if found:
                    break
            if found:
                break
    return bins


def destroy_repack(bins, capacity, max_iters=600, seed=42):
    """Randomly destroy bins, repack items into remaining."""
    rng = random.Random(seed)
    best_count = len(bins)
    best_bins = [list(b) for b in bins]

    for _ in range(max_iters):
        current = [list(b) for b in best_bins]
        cur_rem = [capacity - sum(b) for b in current]
        n = len(current)
        if n <= 2:
            break

        num_destroy = rng.randint(1, min(6, n - 1))
        weights = [cur_rem[i] + 1 for i in range(n)]

        destroy = set()
        for __ in range(num_destroy):
            remaining = [i for i in range(n) if i not in destroy]
            w = [weights[i] for i in remaining]
            tw = sum(w)
            if tw == 0:
                break
            r = rng.random() * tw
            c = 0
            for idx, wt in zip(remaining, w):
                c += wt
                if c >= r:
                    destroy.add(idx)
                    break

        freed = []
        for idx in destroy:
            freed.extend(current[idx])
            current[idx] = []
            cur_rem[idx] = capacity

        if try_fit_greedy(freed, current, cur_rem, capacity, destroy):
            new_bins = [b for i, b in enumerate(current) if i not in destroy]
            if len(new_bins) < best_count:
                best_count = len(new_bins)
                best_bins = new_bins

    return best_bins


def mbs_anchor(items, capacity):
    """MBS with anchor: start each bin with largest remaining item."""
    pool = sorted(items, reverse=True)
    bins = []
    while pool:
        anchor = pool.pop(0)
        space = capacity - anchor
        bin_items = [anchor]
        if space > 0 and pool:
            cands = [(i, w) for i, w in enumerate(pool) if w <= space]
            best_combo = None
            best_slack = space + 1
            mk = min(len(cands), 4)
            for k in range(1, mk + 1):
                if len(cands) > 50 and k > 2:
                    break
                for combo in combinations(range(len(cands)), k):
                    total = sum(cands[j][1] for j in combo)
                    if total <= space:
                        slack = space - total
                        if slack < best_slack:
                            best_slack = slack
                            best_combo = combo
                            if slack == 0:
                                break
                if best_slack == 0:
                    break
            if best_combo is not None:
                idxs = sorted([cands[j][0] for j in best_combo], reverse=True)
                for idx in idxs:
                    bin_items.append(pool[idx])
                    pool.pop(idx)
        bins.append(bin_items)
    return bins


def pair_swap_and_eliminate(bins, capacity):
    """Swap items between bin pairs, then try elimination."""
    rem = [capacity - sum(b) for b in bins]
    rounds = 0
    max_rounds = 3
    while rounds < max_rounds:
        rounds += 1
        swapped = False
        n = len(bins)
        for i in range(n):
            if swapped:
                break
            for j in range(i + 1, n):
                if swapped:
                    break
                for ai in range(len(bins[i])):
                    if swapped:
                        break
                    a = bins[i][ai]
                    for bj in range(len(bins[j])):
                        b = bins[j][bj]
                        if a == b:
                            continue
                        diff = a - b
                        nr_i = rem[i] + diff
                        nr_j = rem[j] - diff
                        if nr_i < 0 or nr_j < 0:
                            continue
                        old_max = max(rem[i], rem[j])
                        new_max = max(nr_i, nr_j)
                        if new_max <= old_max:
                            continue
                        bins[i][ai] = b
                        bins[j][bj] = a
                        rem[i] = nr_i
                        rem[j] = nr_j
                        swapped = True
                        break
        if swapped:
            old_n = len(bins)
            bins = bin_elimination(bins, capacity)
            bins = item_relocation(bins, capacity)
            if len(bins) < old_n:
                rem = [capacity - sum(b) for b in bins]
                rounds = 0
        else:
            break
    return bins


def full_repack_target(items, capacity, target_bins, node_limit=5000000):
    """Try to pack all items into target_bins bins using backtracking."""
    items_sorted = sorted(items, reverse=True)
    n = len(items_sorted)
    bins = [0] * target_bins

    total = sum(items_sorted)
    if total > target_bins * capacity:
        return None

    suffix = [0] * (n + 1)
    for i in range(n - 1, -1, -1):
        suffix[i] = suffix[i + 1] + items_sorted[i]

    count = [0]

    def backtrack(idx):
        if count[0] > node_limit:
            return None
        if idx == n:
            return True
        count[0] += 1
        item = items_sorted[idx]

        rem_cap = sum(capacity - b for b in bins)
        if suffix[idx] > rem_cap:
            return False

        tried_loads = set()
        bin_order = sorted(range(target_bins), key=lambda b: bins[b], reverse=True)
        for b in bin_order:
            if bins[b] + item > capacity:
                continue
            load = bins[b]
            if load in tried_loads:
                continue
            tried_loads.add(load)
            bins[b] += item
            result = backtrack(idx + 1)
            if result is True:
                return True
            bins[b] -= item
            if result is None:
                return None
            if load == 0:
                break
        return False

    result = backtrack(0)
    if result is True:
        return target_bins
    return None


def solve(items, capacity):
    """Try multiple strategies, return the best."""
    results = []

    # Strategy 1: BFD + local search + destroy-repack
    b = bfd_pack(items, capacity)
    b = bin_elimination(b, capacity)
    b = item_relocation(b, capacity)
    b = destroy_repack(b, capacity, max_iters=800, seed=42)
    b = bin_elimination(b, capacity)
    b = item_relocation(b, capacity)
    b = pair_swap_and_eliminate(b, capacity)
    results.append(len(b))

    # Strategy 2: MBS anchor + local search
    b = mbs_anchor(items, capacity)
    b = bin_elimination(b, capacity)
    b = item_relocation(b, capacity)
    for seed in [42, 123, 456]:
        b2 = destroy_repack([list(x) for x in b], capacity, max_iters=600, seed=seed)
        b2 = bin_elimination(b2, capacity)
        b2 = item_relocation(b2, capacity)
        results.append(len(b2))

    # Strategy 3: FFD + local search
    b = ffd_pack(items, capacity)
    b = bin_elimination(b, capacity)
    b = item_relocation(b, capacity)
    b = destroy_repack(b, capacity, max_iters=400, seed=999)
    b = bin_elimination(b, capacity)
    b = item_relocation(b, capacity)
    results.append(len(b))

    best = min(results)

    # Strategy 4: Backtracking for small/medium instances
    if len(items) <= 200:
        lb = -(-sum(items) // capacity)
        n_large = sum(1 for x in items if x > capacity // 2)
        lb = max(lb, n_large)
        node_limit = 10000000 if len(items) <= 100 else 3000000
        for target in range(lb, best):
            r = full_repack_target(items, capacity, target, node_limit=node_limit)
            if r is not None:
                best = r
                break

    return best


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

    result = solve(items, capacity)
    print(result)


if __name__ == "__main__":
    main()
