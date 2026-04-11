# Experiment Objectives

## Primary Goal
Reach optimal TSP tour cost in the fastest possible time across all instance sizes.

## Research Objectives

1. **Maximize solution quality** — minimize gap to known optimal on all holdout instances (berlin52 through pcb3038). Optimality is the target, not just improvement.

2. **Minimize time to optimality** — reduce the wall-clock time needed to first find the optimal tour. Faster convergence through better candidate sets, smarter move selection, and more effective perturbation.

3. **Improve per-trial effectiveness** — each LK trial should produce higher-quality tours by focusing computation on high-potential nodes and moves, using priority-based selection and tighter pruning.

4. **Improve perturbation quality** — escape local optima more effectively so fewer trials are wasted revisiting the same basin of attraction. Adaptive kick strength, guided targeting of stagnant tour regions.

5. **Optimize GA recombination** — explore population size, crossover operators (GPX2/IPT/CLARIST), and replacement strategies to better combine independently found tours.

## Evaluation
- Metric: gap_to_optimal across 12 holdout instances, 5 seeds each
- Timeouts: dynamically adjusted by instance size (quality > speed)
- Success = reaching optimality; secondary = minimizing time to reach it

## Constraints
- Function signatures at module boundaries are frozen (only strategist can unfreeze)
- Shared headers (LKH.h) managed by strategist only
- All changes must compile cleanly with `make -j4`
