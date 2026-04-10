# AlgoForge Design Specification

## Overview

AlgoForge is a hierarchical multi-agent system for automated algorithm discovery and evolution. It orchestrates a strategist agent and configurable parallel researcher agents to evolve codebases toward better performance on defined benchmarks.

The framework is target-agnostic — it works with any codebase in any language. The first test case is evolving a TSP heuristic in C that beats LKH-2 on pure symmetric TSP.

### Three Components

1. **AlgoForge Framework (Python)** — the core product. A hierarchical multi-agent system with CLI interface.
2. **TSP Test Case (C)** — first application. Evolve a heuristic that beats LKH-2 on TSPLIB benchmarks.
3. **LKH-2 Baseline (C)** — original LKH-2 compiled and benchmarked as ground truth.

---

## Agent Architecture

Two agent types. No more.

### Strategist (1 instance)

The research PI. Responsibilities:

- **Initialize** — analyze seed codebase, decompose into modules, run baseline benchmarks
- **Assign** — assign modules to researchers based on priority scores
- **Compose** — periodically merge best module branches, evaluate the combined build
- **Reprioritize** — shift researcher assignments based on evidence
- **Resolve conflicts** — handle git merge conflicts during composition. Only if resolution fails, fall back to cross-pollination mode
- **Report** — at experiment end, document everything: what was tried, what worked, why, final algorithm, benchmark comparison

Priority scoring per module is based on:
- Improvement potential (recent gains = hot area)
- Stagnation (last N experiments all failed = deprioritize)
- Impact weight (domain knowledge about which modules matter most)
- Dependency (module A unlocks module B = prioritize A)

Reassignment triggers:
- Researcher hits max_iterations with no improvement
- New composition reveals a new bottleneck
- Breakthrough in one module opens opportunities in another

### Researcher (N configurable instances)

The worker. Each researcher runs a tight inner loop on its assigned module:

1. **Receive** assignment from strategist (module, files, objective, context from past experiments)
2. **Analyze** the module code
3. **Hypothesize** an improvement (with reasoning)
4. **Implement** the change (edit C source files)
5. **Commit** (`git commit` on the module branch)
6. **Build** (compile full codebase — if it fails, read errors and fix, up to 3 retries)
7. **Evaluate** (run against benchmark instances, collect tour lengths)
8. **Compare** to current best:
   - Better → keep the commit, update module best
   - Worse → `git reset`, log to results.tsv
9. **Log** the experiment (structured TSV entry)
10. **Repeat** from step 3 until max_iterations or strategist reassigns

Evaluation is progressive: start with small TSPLIB instances (50-500 cities) for fast feedback. Promote to larger instances only if small ones improve.

Build failures count as iterations. The researcher maintains a local experiment history to avoid repeating failed ideas. The researcher can be interrupted mid-loop by the strategist.

---

## Operating Modes

### Evolve Mode

Seed code exists. The strategist decomposes it into modules and researchers improve them. Used for the TSP/LKH-2 test case.

### Generate Mode

No seed code. The strategist defines the problem specification and module interfaces. Researchers generate implementations from scratch, guided by the strategist's domain knowledge.

---

## Evolution Strategy

### Primary: Decomposed Module Evolution

- The strategist decomposes the target codebase into modules (e.g., for LKH-2: move operators, candidate edges, perturbation, search control)
- Each researcher is assigned a module with clear file boundaries
- Researchers evolve their module in isolation on a dedicated git branch
- The strategist composes the best version of each module and evaluates the whole
- Natural parallelism without conflicts. Scales cleanly with agent count.

### Fallback: Cross-Pollination (Independent Lineages)

Triggered only when:
- A researcher's improvement spans module boundaries and the strategist cannot resolve the merge conflict
- Module composition degrades performance despite individual improvements (tight coupling the decomposition missed)
- Stagnation across all modules — cross-pollination introduces diversity

In fallback mode, affected researchers fork the full codebase on their own branch and evolve holistically. The strategist can run some researchers in module mode and others in cross-pollination mode simultaneously.

Cross-pollination is a last resort, not a convenience escape. The strategist must attempt conflict resolution first.

---

## State Management

Git is the state manager. No custom filesystem structures.

### Git Branching

- `main` — current best overall composition
- `module/<name>` — each researcher's branch for their assigned module
- `crosspollin/<id>` — full-codebase branches for fallback mode
- Tags mark baselines and milestone compositions

### Project Directory

```
project/
├── config.yaml              # project configuration
├── seed/                    # original code (read-only, tagged in git)
├── results.tsv              # single flat experiment log (append-only)
├── strategist_log.tsv       # strategist decisions
└── benchmarks/              # benchmark instances (e.g., TSPLIB .tsp files)
```

### results.tsv Format

Tab-separated, append-only:

```
timestamp	researcher	module	commit	metric	status	hypothesis	description
2026-04-10T14:30:00	r1	move_operators	a1b2c3d	0.0012	keep	Reorder edge candidate evaluation	Changed sorting in Best2OptMove.c
2026-04-10T14:32:00	r2	candidate_edges	b2c3d4e	0.0015	discard	Increase alpha-nearness threshold	Modified CreateCandidateSet.c threshold
```

### Researcher Loop State

- Edit → `git commit` on module branch
- Better → keep commit (branch advances)
- Worse → `git reset` (branch reverts)
- Full experiment history is in git log + results.tsv

### Strategist Composition

- Merge best module branches into a composition branch
- Build and evaluate against benchmarks
- If better than `main` → fast-forward `main`
- Tag milestone compositions

---

## Model Layer

OpenRouter as the unified model provider. Supports OpenAI, Anthropic, Google, Databricks, AWS Bedrock, Azure, and others through a single API.

Users configure models per agent role. For the TSP test case, Google Gemini models are the defaults:

```yaml
agents:
  strategist:
    model: "google/gemini-2.5-pro"
  researchers:
    count: 4
    model: "google/gemini-2.5-flash"
```

Model swapping is a config string change. No code changes required.

---

## Project Configuration

```yaml
project:
  name: "tsp-heuristic"
  mode: "evolve"                        # evolve | generate
  seed_path: "./seeds/lkh2/"
  language: "c"

modules:                                # strategist can refine these
  - name: "move_operators"
    files: ["SRC/Best2OptMove.c", "SRC/Best3OptMove.c"]
    description: "k-opt move evaluation and selection"
  - name: "candidate_edges"
    files: ["SRC/CreateCandidateSet.c"]
    description: "Alpha-nearness candidate edge generation"
  - name: "perturbation"
    files: ["SRC/LinKernighan.c"]
    description: "Double-bridge and perturbation strategies"

build:
  command: "make -j4"
  binary: "./LKH"

benchmarks:
  small: ["benchmarks/tsplib/eil51.tsp", "benchmarks/tsplib/berlin52.tsp"]
  medium: ["benchmarks/tsplib/rat783.tsp", "benchmarks/tsplib/pr1002.tsp"]
  large: ["benchmarks/tsplib/fl1577.tsp", "benchmarks/tsplib/d2103.tsp"]
  baseline_results: "baselines/lkh2_results.json"

evaluation:
  metric: "gap_to_optimal"              # (tour_length - optimal) / optimal
  progressive: true                     # small first, promote to larger
  runs_per_instance: 5                  # average over multiple runs

agents:
  strategist:
    model: "google/gemini-2.5-pro"
  researchers:
    count: 4
    model: "google/gemini-2.5-flash"
    max_iterations_per_assignment: 20
    timeout_per_iteration: 120          # seconds

stopping_conditions:
  max_total_iterations: 500
  max_hours: 24
  target_improvement: 0.5              # stop if we beat baseline by X%
  stagnation_window: 50                # stop if no improvement in last N iterations
```

The module decomposition in config is a starting hint. The strategist can refine it after analyzing the codebase — split modules further, merge them, change file assignments.

---

## Strategist Lifecycle

```
Phase 1: INITIALIZATION
├── Load project config
├── If evolve mode: analyze seed code, decompose into modules
├── If generate mode: define module interfaces from problem spec
├── Run baseline evaluation (compile + benchmark unmodified code)
├── Build initial knowledge base (codebase analysis)
└── Create initial module priority ranking

Phase 2: RESEARCH (main loop)
├── Assign modules to researchers based on priority scores
├── Monitor researcher progress (results.tsv)
├── Periodically COMPOSE: merge best module branches → build → evaluate
├── Update priority scores based on composition results
├── Detect fallback triggers → switch to cross-pollination (last resort)
├── Reassign researchers on stagnation or breakthroughs
├── Resolve merge conflicts (must attempt before fallback)
├── Check stopping conditions after each composition
└── Repeat until stopping condition triggers

Phase 3: REPORT
├── Analyze full experiment history
├── Document what was tried, what worked, what didn't, and why
├── Describe the final evolved algorithm
├── Produce benchmark comparison (evolved vs baseline)
└── Write structured report to report/

Phase 4: CLEANUP
├── Save final evolved codebase (main branch)
├── Save full experiment logs
└── Save report
```

---

## Stopping Conditions

Configurable. User picks one or more:

```yaml
stopping_conditions:
  max_total_iterations: 500         # hard cap on total experiments
  max_hours: 24                     # wall clock limit
  target_improvement: 0.5           # stop if baseline beaten by X%
  stagnation_window: 50             # stop if no improvement in last N iterations
```

The strategist evaluates these after each composed build. When any condition triggers, it stops all researchers (finish current iteration) and enters report mode.

---

## CLI Interface

```bash
algoforge init --seed ./lkh2-src --config config.yaml   # initialize project
algoforge run config.yaml                                 # start experiment
algoforge status                                          # check progress
algoforge stop                                            # graceful stop → report
algoforge report                                          # generate report from completed run
```

## Claude Code Plugin

Thin wrapper over the CLI:

```
/algoforge-init     → algoforge init
/algoforge-start    → algoforge run (background)
/algoforge-status   → reads results.tsv + strategist_log.tsv, summarizes
/algoforge-stop     → sends stop signal
/algoforge-report   → algoforge report
```

The plugin adds interactive mode: user can chat with the strategist mid-run to ask about decisions, suggest directions, or override priorities.

---

## Codebase Structure

```
algoforge/
├── __init__.py
├── cli.py              # CLI entry point (click or argparse)
├── config.py           # config loading and validation
├── strategist.py       # strategist agent logic
├── researcher.py       # researcher agent loop
├── eval.py             # build + benchmark runner
└── models.py           # OpenRouter client
```

Six core files. The plugin is a separate package that depends on algoforge.

---

## TSP Test Case: Setup Steps

1. Download LKH-2 source from Helsgaun's site
2. Compile and verify it runs on the target machine
3. Download TSPLIB benchmark instances
4. Run LKH-2 against all benchmark tiers (small/medium/large)
5. Record baseline results
6. Configure algoforge project with LKH-2 as seed
7. Run algoforge
