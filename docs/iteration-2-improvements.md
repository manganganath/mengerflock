# AlgoForge — Iteration 2 Improvement Log

Run duration: ~45 minutes. 24 experiments logged. 3 researchers + 1 strategist.

Fixes applied from iteration 1: eval.sh macOS compat, researcher prompt path resolution, mandatory logging, strategist Phase 2 persistence.

## Results Summary

### Baseline
- avg_gap = 0.0122% across large tier (fl1577: 0.054%, d2103: 0.046%, pcb3038: 0.000%)
- All small/medium instances optimal (0% gap)

### Best Composition (composition-1, merged to main)
- avg_gap = 0.0090% (26% improvement over baseline)
- best_gap = 0.0024% (69% improvement)
- fl1577: found OPTIMAL TOUR on some seeds
- Combined r1's inner-loop early termination + r2's subgradient tuning

### Individual Researcher Best Results
| Researcher | Module | Best Change | d2103 gap | pcb3038 gap |
|---|---|---|---|---|
| baseline | — | — | 0.105% | 0.043% |
| r1 | move_operators | break on gain criterion fail | 0.047% | 0.008% |
| r2 | candidate_edges | 2-step polishing + warm-start | 0.017% | 0.0005% |
| r3 | perturbation | (no successful mutations) | — | — |

### Experiment Breakdown
- r1: 6 experiments (1 keep, 5 discards)
- r2: 12 experiments (10 keeps, 2 discards)
- r3: 6 experiments (1 baseline keep, 2 discards, 3 crashes)
- Total: 24 experiments, 2 genuine improvements found

## Issues Found

### 1. Keep/discard on 0% gap baseline is meaningless
When LKH-2 already finds optimal on small instances, every non-crashing change gets kept. r2 had 8 "keeps" at 0% gap before moving to large tier. Researchers should auto-promote to larger tiers when small tier is saturated.

### 2. Strategist too slow on Phase 1
Spent ~15 minutes on exhaustive baselines and domain research before entering Phase 2. Meanwhile researchers were already iterating. Should do quick baseline (small tier only) and refine during Phase 2.

### 3. Composition conflict between r1 and r2
Composition 2 was DISCARDED: r2's Polyak+polishing preprocessing overhead cancelled r1's early-termination speedup. The strategist correctly identified this: "Preprocessing overhead eats into trial time." Composition strategy needs to account for speed vs quality tradeoffs.

### 4. r3 completely stagnant on large tier
4 crashes, 0 successful keeps on large instances. Every approach added computation (extra LK calls, relaxed search). The strategist identified: "need to make trials FASTER not add work" but r3 didn't find a way to do that in the perturbation module.

### 5. Large-instance evaluation bottleneck
Iteration speed dropped from ~1/min (small tier) to ~1/5-7min (large tier). Each large instance takes 1-2 min × 5 seeds. Consider: 1-seed screening first, full 5-seed only for promising changes.

### 6. r1 couldn't find assignment file
r1 self-bootstrapped from branch name because PROJECT_ROOT discovery didn't resolve to the correct path. The assignment files existed but r1 looked locally.

### 7. Researchers have very different iteration speeds
After 45 min: r2 had 12 experiments, r1 had 6, r3 had 6. r2 iterated fast on small tier early, then slowed on large. r1 was thorough but slow throughout.

### 8. macOS bash compatibility
Strategist hit `declare -A` error (bash 3.x on macOS doesn't support associative arrays). Fell back to Python. eval.sh fixes from iteration 1 worked.

## Positive Observations

### P1. results.tsv logging works
The PROJECT_ROOT path fix from iteration 1 completely resolved the logging issue. 24 experiments logged reliably.

### P2. Strategist self-corrected on tier assignment
Read r3's note in results.tsv ("small-tier saturated") and reassigned ALL researchers to target medium+large tiers. Filesystem communication worked as designed.

### P3. Strategist performed composition
Merged r1 + r2 improvements into composition-1, evaluated, found 26% improvement, merged to main. Also correctly discarded composition-2 when it regressed.

### P4. Strategist derived insights from researcher patterns
Watched r3's crash pattern and concluded: "60s timeout means we need to make trials FASTER not add work." This is hierarchical reasoning working as intended.

### P5. r1 found a real algorithmic improvement
"break instead of continue when gain criterion fails" — 51% gap reduction on large tier. Simple but effective: sorted candidates mean once gain goes negative, all subsequent ones will too.

### P6. r2 found significant subgradient improvements
Warm-start Pi, slower T decay, 2-step polishing — d2103 gap from 0.104% to 0.017%. Nearly optimal on pcb3038 (0.0005%).

### P7. r3 learned through systematic failure
4 crashes each revealed something: KSwapKick not called with KickType=0, extra LK calls too expensive at 20s each, relaxing search adds work. Good research methodology even though no successful mutation was found.

### P8. r2 good scientific methodology
Tested extreme parameters (9/10 momentum), found small instances insensitive, reverted to literature values. Disciplined approach.

## Fixes Needed for Iteration 3

1. **Auto-promote to larger tiers** when small tier gap = 0%
2. **1-seed screening** before full 5-seed evaluation on large instances
3. **Faster strategist Phase 1** — quick baseline, iterate during Phase 2
4. **Composition-aware evaluation** — test whether module improvements conflict before merging
5. **Symlink state/ into worktrees** instead of relying on PROJECT_ROOT discovery
6. **r3 needs different strategy** — perturbation module may need a fundamentally different approach (reduce per-trial cost rather than add post-processing)
