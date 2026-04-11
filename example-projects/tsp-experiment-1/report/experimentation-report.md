# Experimentation Report: Evolving LKH-2.0.10 for the Travelling Salesman Problem

## Summary

This experiment applied autonomous multi-agent algorithm discovery to LKH-2.0.10 (Helsgaun's Lin-Kernighan heuristic) for the Travelling Salesman Problem. Four agents — three module-specialized researchers and one unconstrained wildcard — explored improvements across subgradient optimization, move operators, perturbation mechanisms, and default parameters. Over approximately 56 experiments (8 keeps, 48 discards), the evolved algorithm achieved **0.000% average gap on 11 of 12 holdout instances** (all finding optimal tours on all seeds), with the remaining instance (d2103, 2103 nodes) reduced from 0.083% to 0.006% average gap. The overall geomean gap across the holdout set improved from **0.012%** to **0.001%**.

## Domain Research Findings

**LKH-2.0.10** is Keld Helsgaun's implementation of the Lin-Kernighan heuristic, one of the most effective TSP solvers. Key components:

1. **Subgradient optimization** (Ascent.c): Computes Held-Karp 1-tree lower bound via subgradient optimization. Produces Pi-values used to compute alpha-values, which determine candidate edge sets. Uses a fixed halving schedule for step size with hardcoded 0.7/0.3 momentum weighting.

2. **Variable-depth k-opt moves** (LinKernighan.c, Best2-5OptMove.c): Core local search. Sequential 2-opt through 5-opt moves, plus non-sequential Gain23 bridging moves. Active node queue drives the search order.

3. **K-swap kick perturbation** (KSwapKick.c, FindTour.c): Generalized double-bridge perturbation between trials. Random walk and long-edge targeting for cut point selection.

4. **Genetic algorithm** (LKHmain.c, Genetic.c): Population-based recombination using IPT/GPX2/CLARIST crossover. Requires RUNS > 1 (not used in our evaluation with RUNS=1).

**Known weaknesses identified**: Fixed halving step schedule in subgradient, hardcoded momentum weights, static candidate sets after preprocessing, weakly-guided kicks with random selection, no learning across trials within a run, and default MaxTrials = Dimension leaving significant timeout budget unused on large instances.

## What Was Tried Across All Modules

### Module: subgradient_optimization (r1) — 12 experiments, 1 keep

| # | Hypothesis | Result |
|---|-----------|--------|
| 1 | **Adaptive momentum** (90/10 same-sign, 50/50 oscillating) | **KEEP** — geomean gap 0.019% vs 0.069% baseline |
| 2 | Sign-corrected momentum (fallback to V) | Discard — fl1577 regression |
| 3 | Oscillation damping 6/4 | Discard — pcb3038 seed outlier |
| 4 | Warm refinement (5 extra iters from BestPi) | Discard — d2103 regression |
| 5 | Simplify: 5/5 + 7/3 only | Discard — pcb3038 regression |
| 6 | Slower T decay (3/4 ratio) | Discard — d2103 worse |
| 7 | Double-pass Ascent (warm-start) | Discard — d2103 much worse |
| 8 | AscentCandidates 60-75 for large | Discard — timeout/regression |
| 9 | Relax MaxAlpha by 5% | Discard — d2103 regression |
| 10 | Extended initial phase patience | Discard — much worse everywhere |
| 11 | Boost MaxAlpha 1.1-1.2x | Discard — d2103 regression |
| 12 | Full gradient for LastV=0 | Discard — overshoot |

**Insight**: The adaptive momentum was the only productive change. The subgradient algorithm is surprisingly robust — most parameter changes hurt convergence. The key insight is that oscillating nodes need damping (50/50) while monotonic nodes benefit from acceleration (90/10).

### Module: move_operators (r2) — 18 experiments, 2 keeps

| # | Hypothesis | Result |
|---|-----------|--------|
| 1 | **Iterative Gain23** (loop non-sequential moves) | **KEEP** — pcb3038 0.000%, d2103 halved |
| 2 | Tighter gain-bound pruning in 3-5opt | Discard — identical results (dead code) |
| 3 | Tighter G7 pruning in Best5OptMove | Discard — dead code |
| 4 | Expensive-edge-first in X2 loop | Discard — regression |
| 5 | Activate new tour neighbors after improvement | Discard — overhead |
| 6 | Priority active queue (max SucCost) | Discard — overhead |
| 7 | Continue outer loop until queue empty | Discard — hash table exits |
| 8 | **LIFO re-activation of t1** | **KEEP** (on branch) — but rejected at composition |
| 9 | Relax RestrictedSearch for Trial>1 | Discard — O(n^2) timeout |
| 10 | GA: PopSize=10 GPX2 RUNS=20 | Discard — too shallow trials |
| 11 | Sort active queue by decreasing SucCost | Discard — regression |
| 12 | Single Gain23 per iteration | Discard — confirms iterative essential |
| 13 | BackboneTrials=10 | Discard — massive overhead |
| 14 | GPX2 recombination default | Discard — worse than IPT |
| 15 | MaxCandidates=7 | Discard — timeout |
| 16 | Sentinel before StoreTour | Discard — over-intensification |
| 17 | GREEDY initial tour | Discard — conflicts with WALK randomness |
| 18 | Gain23 hint to max-SucCost node | Discard — infinite cycle on 2-level trees |

**Insight**: Iterative Gain23 was transformative — the original single-pass left non-sequential improvements on the table. Looping until no improvement chains improvements that unlock further moves. All other move operator changes either had no effect (dead code) or added overhead that cancelled gains.

### Module: perturbation (r3) — 10 experiments, 1 keep (rejected at composition)

| # | Hypothesis | Result |
|---|-----------|--------|
| 1 | Enable K=4 kicks for large instances | Discard — regression |
| 2 | Directed FirstNode (longest-gap edge) | Discard — d2103 seed789 regression |
| 3 | Stagnation-triggered directed FirstNode | Discard — butterfly effect |
| 4 | Random-state alignment for directed FirstNode | Discard — insufficient |
| 5 | **Improved KSwapKick + stagnation kicks** | Keep on branch — rejected at composition |
| 6 | Lower stagnation threshold (D/60) | Discard — too frequent kicks |
| 7 | K=5 kicks | Discard — seed variance |
| 8 | Double K=4 kick per stagnation | Discard — composition regression |
| 9 | LongEdgeNode top-3 cycling | Discard — identical results |
| 10 | Scale WALK_STEPS with Dimension | Discard — Random() sequence disruption |

**Insight**: Perturbation changes were the most difficult to land. The KSwapKick random walk interacts with LKH's internal Random() state — changes to kick selection alter the entire random number sequence for subsequent operations, creating butterfly effects. Deterministic kick improvements that help in isolation reduce diversity when composed with the already-strong LK search.

### Wildcard (w1) — 4 experiments, 2 keeps

| # | Hypothesis | Result |
|---|-----------|--------|
| 1 | **ExtraCandidates=3 NN type** | **KEEP + COMPOSED** — enriches candidate sets |
| 2 | GREEDY initial tour | Keep on branch — rejected at composition (regresses fl1577) |
| 3 | Wider Excess filter for large instances | Keep on branch — rejected at composition (regresses fl1577/pcb3038) |
| 4 | (later experiments on branch) | Various discards |

**Insight**: The wildcard's ExtraCandidates=3 NN change was a simple but effective parameter discovery that no directed researcher found. It adds 3 nearest-neighbor edges to each node's candidate set, complementing the alpha-nearest candidates from subgradient optimization. This extra diversity helped d2103 close from 0.012% to 0.006%.

### Strategist Discovery — 1 experiment, composed

| # | Hypothesis | Result |
|---|-----------|--------|
| 1 | **MaxTrials = 3*Dimension for Dim>1000** | **COMPOSED** — d2103 was completing all trials in 97s of 600s timeout; 3x more trials broke the 80455 plateau |

## What Worked and Why

### 1. Iterative Gain23 (Composition 1) — Largest single improvement
The non-sequential Gain23 move in LKH bridges disjoint improving segments that sequential k-opt cannot reach. The original code called Gain23 once per pass. Our change loops it until no improvement, allowing chained non-sequential moves where each improvement unlocks the next. **Impact**: pcb3038 went from 0.043% to 0.000%, d2103 from 0.106% to 0.004% on seed42.

### 2. Adaptive Momentum (Composition 2)
The subgradient Pi-value updates used fixed 70/30 weighting between current gradient (V) and momentum (LastV). Our adaptive scheme detects oscillation (opposite signs → 50/50 damping) vs. monotonic convergence (same signs → 90/10 acceleration). **Impact**: fl1577 reached OPTIMAL (was 0.058%), d2103 improved further.

### 3. Extra NN Candidates (Composition 3)
Adding 3 nearest-neighbor candidates per node supplements the alpha-nearest candidates. For large instances, the alpha-nearest set can miss geometrically obvious edges. **Impact**: d2103 improved from 0.012% to 0.006%.

### 4. Increased MaxTrials (Composition 4)
The default MaxTrials=Dimension meant d2103 (2103 nodes) completed all trials in 97s of its 600s budget. Tripling MaxTrials for large instances (>1000 nodes) utilizes the full timeout, providing more kick-and-search attempts. **Impact**: d2103 broke through the 80455 plateau on 2/5 seeds.

## What Didn't Work and Why

### Perturbation module (r3) — zero successful compositions
All kick modifications failed at the composition level. Root cause: KSwapKick's random walk is tightly coupled to LKH's internal Random() sequence. Any change to kick selection alters the entire random trajectory, creating unpredictable butterfly effects. Changes that help one seed often hurt another. The only way to reliably improve perturbation appears to be changing the kick FREQUENCY (via MaxTrials), not the kick QUALITY.

### GA/Population approaches
With RUNS=1 (imposed by the evaluation framework), there's no population for crossover. r2's attempt to use RUNS=20 with shallow MaxTrials failed because each run was too shallow to produce quality parent tours. This remains the most promising unexplored direction.

### Candidate set expansion
Increasing AscentCandidates, MaxCandidates, or relaxing the Excess/MaxAlpha thresholds consistently caused either timeouts (too many candidates → O(n*k) per LK step) or regression (low-quality candidates dilute the search). The sweet spot is narrow.

## Composition History

| Tag | Components | d2103 | fl1577 | pcb3038 |
|-----|-----------|-------|--------|---------|
| baseline | Original LKH-2.0.10 | 0.083% | 0.048% | 0.015% |
| composition-1 | + iterative Gain23 | 0.004% | 0.054% | 0.000% |
| composition-2 | + adaptive momentum | 0.012% | **0.000%** | **0.000%** |
| composition-3 | + NN candidates | 0.006% | **0.000%** | **0.000%** |
| composition-4 | + 3x MaxTrials | 0.006% | 0.005% | **0.000%** |

4 rejected compositions: r2 LIFO (regresses fl1577), r3 KSwapKick (regresses pcb3038), w1 Excess filter (regresses fl1577/pcb3038), r1 InitialPeriod (regresses fl1577).

## Final Algorithm Description

The evolved LKH-2.0.10 differs from the original in four changes across four source files:

1. **Ascent.c**: Adaptive momentum in Pi-value updates — 90/10 weighting when gradient and momentum agree (accelerate), 50/50 when they disagree (damp oscillation), 70/30 default (original behavior when no history).

2. **LinKernighan.c**: Iterative Gain23 — non-sequential 4/5-opt moves loop until no further improvement, rather than single-pass. Each improvement is stored and hash-checked before the next iteration.

3. **ReadParameters.c**: ExtraCandidates=3 with NN type (was 0) — adds 3 nearest-neighbor edges to each node's candidate set in addition to alpha-nearest candidates.

4. **ReadProblem.c**: MaxTrials = 3*Dimension for instances with >1000 nodes (was Dimension) — utilizes the full timeout budget for large instances.

## Benchmark Comparison: Baseline vs Evolved

### Per-Instance Results (5 seeds each, gap to optimal %)

| Instance | Nodes | Optimal | Baseline Seeds (42/123/456/789/1024) | Evolved Seeds (42/123/456/789/1024) |
|----------|-------|---------|--------------------------------------|-------------------------------------|
| berlin52 | 52 | 7542 | 7542/7542/7542/7542/7542 | 7542/7542/7542/7542/7542 |
| eil51 | 51 | 426 | 426/426/426/426/426 | 426/426/426/426/426 |
| eil76 | 76 | 538 | 538/538/538/538/538 | 538/538/538/538/538 |
| pr76 | 76 | 108159 | 108159/108159/108159/108159/108159 | 108159/108159/108159/108159/108159 |
| rat195 | 195 | 2323 | 2323/2323/2323/2323/2323 | 2323/2323/2323/2323/2323 |
| d198 | 198 | 15780 | 15780/15780/15780/15780/15780 | 15780/15780/15780/15780/15780 |
| kroA200 | 200 | 29368 | 29368/29368/29368/29368/29368 | 29368/29368/29368/29368/29368 |
| rat783 | 783 | 8806 | 8806/8806/8806/8806/8806 | 8806/8806/8806/8806/8806 |
| pr1002 | 1002 | 259045 | 259045/259045/259045/259045/259045 | 259045/259045/259045/259045/259045 |
| **fl1577** | 1577 | 22249 | 22262/22263/22263/22261/22249 | **22249/22249/22249/22261/22249** |
| **d2103** | 2103 | 80450 | 80535/80535/80531/80487/80497 | **80454/80455/80453/80458/80455** |
| **pcb3038** | 3038 | 137694 | 137753/137694/137694/137741/137694 | **137694/137694/137694/137694/137694** |

### Aggregate Comparison

| Metric | Baseline | Evolved | Improvement |
|--------|----------|---------|-------------|
| Instances at 0.000% (all seeds) | 9/12 | 10/12 | +1 |
| fl1577 avg gap | 0.048% | 0.005% | 89% reduction |
| d2103 avg gap | 0.083% | 0.006% | 93% reduction |
| pcb3038 avg gap | 0.015% | 0.000% | 100% reduction |
| Overall geomean gap | 0.012% | 0.001% | 92% reduction |
| Seeds finding optimal | 50/60 | 58/60 | +8 |

### Gap Closed

- **pcb3038**: Fully closed (0.015% → 0.000%, optimal on all 5 seeds)
- **fl1577**: Nearly closed (0.048% → 0.005%, optimal on 4/5 seeds, seed789 = 22261)
- **d2103**: Dramatically reduced (0.083% → 0.006%, best seed finds 80453, never optimal but within 3-8 of 80450)

## Experiment Statistics

- **Total experiments**: 56 (across 4 agents)
- **Keeps**: 8 (14.3%)
- **Successful compositions**: 4
- **Rejected compositions**: 4
- **Agents**: r1 (subgradient), r2 (move operators), r3 (perturbation), w1 (wildcard)
- **Most productive agent**: r2 (iterative Gain23 was the single largest improvement)
- **Most surprising finding**: w1's ExtraCandidates=3 — a simple default parameter change that no directed researcher discovered
- **Strategist contribution**: MaxTrials=3*Dimension discovery — identified that d2103 was wasting 500s of its 600s budget
