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

No seed code. The strategist defines the problem specification and module interfaces from the config. Researchers generate implementations from scratch, guided by the strategist's domain knowledge.

In generate mode:
- The strategist creates empty module files with interface stubs (function signatures, expected inputs/outputs)
- Researchers implement the module internals from scratch
- The first few iterations focus on producing code that compiles and produces valid output (correctness before optimization)
- Once a working baseline exists, the normal evolve loop takes over (improve the metric)

The config must provide:
- `problem_spec`: description of the problem and expected I/O format
- `modules`: module names with interface descriptions (instead of file paths)
- `build` and `benchmarks`: same as evolve mode
- `reference_materials` (optional): papers, pseudocode, or documentation the researchers can reference

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

Git manages code versioning. Shared state files live outside git.

### Git Branching

- `main` — current best overall composition
- `module/<name>` — each researcher's branch for their assigned module
- `crosspollin/<id>` — full-codebase branches for fallback mode
- Tags mark baselines and milestone compositions

### Git Worktrees for Concurrency

Each researcher operates in its own `git worktree`. This is required because multiple researchers cannot share a single working directory — `git checkout` on one branch would clobber another researcher's files.

On initialization:
- The strategist creates one worktree per researcher: `git worktree add .worktrees/r<id> module/<name>`
- Each researcher works exclusively in its worktree
- The strategist operates in the main working directory

Worktrees are created/destroyed as researchers are assigned/reassigned. They are lightweight (shared `.git` objects) but provide full filesystem isolation.

### Project Directory

```
project/
├── config.yaml              # project configuration
├── seed/                    # original code (read-only, tagged in git)
├── state/                   # shared state (outside git)
│   ├── results.tsv          # single flat experiment log (append-only)
│   └── strategist_log.tsv   # strategist decisions
├── benchmarks/              # benchmark instances (e.g., TSPLIB .tsp files)
└── .worktrees/              # git worktrees (one per researcher)
    ├── r1/
    ├── r2/
    └── ...
```

`state/` lives outside git so all agents can read/write it regardless of branch. File-level locking (e.g., `fcntl.flock`) prevents concurrent append corruption.

### results.tsv Format

Tab-separated, append-only:

```
timestamp	researcher	module	commit	metric_avg	metric_best	status	hypothesis	description
2026-04-10T14:30:00	r1	move_operators	a1b2c3d	0.0012	0.0008	keep	Reorder edge candidate evaluation	Changed sorting in Best2OptMove.c
2026-04-10T14:32:00	r2	candidate_edges	b2c3d4e	0.0015	0.0011	discard	Increase alpha-nearness threshold	Modified CreateCandidateSet.c threshold
```

### strategist_log.tsv Format

```
timestamp	action	details
2026-04-10T14:00:00	init	Decomposed into 3 modules: move_operators, candidate_edges, perturbation
2026-04-10T14:35:00	compose	Merged module/move_operators + module/candidate_edges → avg gap 0.0010
2026-04-10T14:36:00	reassign	Moved r3 from candidate_edges to perturbation (stagnation after 15 iterations)
```

### Researcher Loop State

- Edit → `git commit` on module branch (in worktree)
- Better → keep commit (branch advances)
- Worse → `git reset --hard HEAD~1` (reverts to previous commit; safe because the researcher just committed)
- Full experiment history is in git log + state/results.tsv

### Strategist Composition

- Merge best module branches into a composition branch
- Build and evaluate against benchmarks
- If better than `main` → fast-forward `main`
- Tag milestone compositions

---

## LLM Interaction Protocol

### Researcher Prompt Structure

Each researcher iteration sends the following context to the model:

1. **System prompt** — role description, constraints (only edit assigned files, must compile, etc.)
2. **Module source** — full content of the assigned files. For large files, the strategist may provide a summarized version with key sections highlighted.
3. **Assignment** — objective text from the strategist, specific areas to explore
4. **Recent experiment history** — last 10-20 entries from results.tsv for this module (not the full history). Includes hypothesis, result, and keep/discard status so the model avoids repeating failures.
5. **Build/eval feedback** — on retry iterations: compiler errors or benchmark output from the previous attempt

The model responds with:
- Hypothesis (one sentence)
- Code edits as **search/replace blocks** (file path, old text, new text). This format is more reliable than unified diffs for LLM-generated edits. For small files (<200 lines), the model may return the full file content instead.
- Reasoning (why this should improve the metric)

The framework applies edits by: (1) validating the old text exists in the file, (2) replacing with new text, (3) if the old text is not found (LLM hallucination), asking the model to retry with the actual file content. Full file rewrites are applied directly.

### Strategist Prompt Structure

1. **System prompt** — role as research PI, responsibilities, decision framework
2. **Codebase summary** — module list with file sizes, key functions, and inter-module dependencies (not full source)
3. **Full results.tsv** — complete experiment history across all researchers
4. **Current state** — which researcher is on which module, iteration counts, latest composition result
5. **Decision request** — "compose now?", "reassign researchers?", "switch to cross-pollination?"

### Context Management

- **Token budget**: each researcher call should stay under 50% of the model's context window, leaving room for the response. For Gemini Flash (1M context), this is generous. For smaller models, the strategist provides summarized module source instead of full files.
- **History pruning**: only the last N experiments per module are included in researcher prompts. The strategist sees the full history.
- **Large files**: if a module file exceeds 1000 lines, the strategist provides an annotated summary (key functions, data structures, hot paths) alongside the full source. The researcher can request specific line ranges.

### Assignment Data Structure

```python
@dataclass
class Assignment:
    module_name: str
    files: list[str]              # paths relative to repo root
    objective: str                # what to improve and why
    constraints: list[str]        # e.g., "do not change function signatures in LKH.h"
    context: str                  # strategist's notes on what's been tried and what's promising
    recent_experiments: list[dict] # last N experiments for this module
```

---

## Evaluation & Metrics

### Metric Definition

Primary metric: **gap_to_optimal** = `(tour_length - optimal) / optimal`

Where `optimal` is the known best solution for each TSPLIB instance.

### Aggregation

- **Per-instance**: run the solver `runs_per_instance` times (default 5) using **fixed random seeds** for reproducibility. Take the **mean** of all runs as the instance score.
- **Per-tier**: compute the **geometric mean** of per-instance gaps across all instances in the tier. Geometric mean prevents a single outlier instance from dominating.
- **Overall**: the primary comparison metric is the geometric mean gap on the **small** tier (for researcher keep/discard) or **all tiers** (for strategist composition evaluation).

### Keep/Discard Decision

A researcher keeps a mutation if:
- The geometric mean gap on the small tier is **strictly lower** than the current module best
- The mutation does not cause any instance to regress by more than 2x its current gap (prevents trading broad improvement for catastrophic regression on one instance)

### Progressive Evaluation

1. **Small tier first** — every mutation is evaluated here. Fast feedback (~seconds per instance).
2. **Promotion to medium** — if a mutation survives 3 consecutive keep decisions on small, it is also evaluated on medium tier.
3. **Promotion to large** — only during strategist composition. The composed build is evaluated on all tiers.
4. **No demotion** — once promoted, the researcher continues evaluating on all promoted tiers.

---

## Module Coupling & Shared Dependencies

### The Problem

In real codebases, modules are not perfectly isolated. In LKH-2 specifically:
- `LinKernighan.c` (perturbation module) calls functions defined in `Best2OptMove.c`, `Best3OptMove.c` (move operators module)
- Shared header files (`LKH.h`) define data structures used by all modules
- Changing a function signature in one module breaks callers in another

### Rules

1. **Shared headers are owned by the strategist**, not any researcher. If a researcher needs a header change, it proposes the change to the strategist, who applies it to `main` and propagates to all worktrees.
2. **Function signatures at module boundaries are frozen by default**. A researcher can change internals freely but must not change the signature of functions called by other modules. If a signature change is necessary, the researcher flags it to the strategist.
3. **The strategist tracks inter-module dependencies** during initialization by analyzing `#include` directives and function call graphs. This informs module decomposition — tightly coupled files go in the same module.

---

## Concurrency Model

The strategist and researchers run as **separate asyncio tasks** within a single Python process.

```
Main process (asyncio event loop)
├── Strategist task (1)
│   - Polls state/results.tsv on a timer (every 30s)
│   - Makes LLM calls for composition decisions, reassignment
│   - Writes to state/strategist_log.tsv
│   - Communicates with researchers via shared asyncio.Queue per researcher
├── Researcher task (N)
│   - Each runs its own inner loop independently
│   - Makes LLM calls, runs build/eval as subprocess
│   - Appends to state/results.tsv (with file locking)
│   - Checks its queue for interrupt signals from strategist
└── Signal handler
    - SIGINT/SIGTERM → sets a shutdown flag
    - All tasks check the flag and finish current iteration before exiting
```

**Strategist → Researcher communication:**
- **Assignment**: strategist puts an `Assignment` message on the researcher's queue
- **Interrupt/Reassign**: strategist puts a `Reassign` message; researcher finishes current iteration then picks up the new assignment
- **Shutdown**: strategist puts a `Stop` message; researcher finishes and exits

**Researcher → Strategist communication:**
- Via `state/results.tsv` (append-only, file-locked). The strategist polls this file.
- No direct messages back — the strategist infers researcher state from the log.

Build and benchmark commands run as async subprocesses (`asyncio.create_subprocess_exec`) so they don't block the event loop.

---

## Error Handling & Recovery

### LLM API Failures

- Retry with exponential backoff (3 attempts, 2s/4s/8s delays)
- If all retries fail, the researcher pauses and reports to the strategist
- The strategist can reassign the module to another researcher or wait

### Build Failures

- Researcher reads compiler errors and attempts a fix (up to 3 retries per iteration)
- If unfixable, `git reset --hard HEAD~1`, log as `crash` in results.tsv, move to next hypothesis
- Build failures count toward the iteration budget

### Evaluation Failures

- If the binary compiles but crashes or hangs on a benchmark instance: kill after `timeout_per_iteration`, treat as `crash`
- If the binary produces invalid output (e.g., tour visits a city twice): treat as `crash`
- Researcher reverts and logs the failure

### Git State Corruption

- Each researcher's worktree is disposable. If corrupted: delete the worktree, recreate from the module branch, resume
- The strategist checks worktree health before each assignment

### Strategist LLM Failures

- Same retry policy as researchers (3 attempts, exponential backoff)
- If all retries fail, the strategist pauses all researchers and waits for the API to recover (retry every 60s)
- If the strategist is down for more than 10 minutes, log a warning to strategist_log.tsv. Researchers continue their current assignments independently — they don't need the strategist for their inner loop.

### System Crash Recovery

- On startup, `algoforge run` checks for an existing `state/` directory
- If found, it resumes: reads results.tsv to reconstruct progress, verifies branch states, restarts researchers from their last known good commit
- The strategist re-evaluates priorities based on recovered state

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
  command: "make -j4"                 # incremental build (fast). Use "make clean && make -j4" if Makefile deps are unreliable
  binary: "./LKH"                     # relative to worktree root

benchmarks:
  small: ["benchmarks/tsplib/eil51.tsp", "benchmarks/tsplib/berlin52.tsp"]
  medium: ["benchmarks/tsplib/rat783.tsp", "benchmarks/tsplib/pr1002.tsp"]
  large: ["benchmarks/tsplib/fl1577.tsp", "benchmarks/tsplib/d2103.tsp"]
  baseline_results: "baselines/lkh2_results.json"

evaluation:
  metric: "gap_to_optimal"              # (tour_length - optimal) / optimal
  progressive: true                     # small first, promote to larger
  runs_per_instance: 5                  # mean over multiple runs
  random_seeds: [42, 123, 456, 789, 1024]  # fixed seeds for reproducibility

agents:
  strategist:
    model: "google/gemini-2.5-pro"
  researchers:
    count: 4
    model: "google/gemini-2.5-flash"
    max_iterations_per_assignment: 20

timeouts:
  llm_call: 60                          # seconds per LLM API call
  build: 30                             # seconds for compilation
  eval_per_instance: 30                 # seconds per benchmark instance per run

stopping_conditions:
  max_total_iterations: 500
  max_hours: 24
  target_improvement: 0.5              # stop if we beat baseline by X%
  stagnation_window: 50                # stop if no improvement in last N iterations
  max_cost_usd: 50.0                  # stop if total LLM API cost exceeds budget (optional)
```

Note: `target_improvement: 0.5` means 0.5% absolute reduction in gap_to_optimal. If the baseline gap is 2.0%, a target of 0.5 means stop when the gap reaches 1.5% or lower.

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
├── COMPOSE when triggered (see Composition Timing below)
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

Additionally, `max_total_iterations` and `stagnation_window` are checked by the strategist between compositions (by reading results.tsv) so they can trigger a stop without waiting for the next composition cycle.

### Composition Timing

The strategist triggers a composition when any of these occur:
- A researcher reports a new module-level best (a `keep` entry in results.tsv)
- A configurable time interval passes with no composition (default: 10 minutes)
- The strategist is about to reassign researchers (compose first to get the latest baseline)

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

The plugin adds interactive mode (v2): user can chat with the strategist mid-run to ask about decisions, suggest directions, or override priorities.

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
├── git_ops.py          # git worktree, branch, merge, reset operations
└── models.py           # OpenRouter client
```

Seven core files. The plugin is a separate package that depends on algoforge.

---

## TSP Test Case: Setup Steps

1. Download LKH-2 source from Helsgaun's site
2. Compile and verify it runs on the target machine
3. Download TSPLIB benchmark instances
4. Run LKH-2 against all benchmark tiers (small/medium/large)
5. Record baseline results
6. Configure algoforge project with LKH-2 as seed
7. Run algoforge
