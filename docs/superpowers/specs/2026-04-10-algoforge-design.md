# AlgoForge Design Specification

## Overview

AlgoForge is a hierarchical multi-agent system for automated algorithm discovery and evolution. It uses existing coding agents (Claude Code, Codex, etc.) as the intelligence layer and provides a thin orchestration layer to coordinate them.

The framework is target-agnostic — it works with any codebase in any language. The first test case is evolving a TSP heuristic in C that beats LKH-2 on pure symmetric TSP.

### Core Insight

Coding agents (Claude Code, Codex, Cursor) already know how to read files, edit code, run commands, handle errors, use git, and search the web. AlgoForge does not rebuild these capabilities. Instead, it launches multiple coding agent sessions, each pointed at a markdown instruction file, and coordinates them — exactly like AutoResearch, but with a hierarchy and parallelism.

### Three Components

1. **AlgoForge Framework (Python)** — a thin orchestrator that launches and manages coding agent sessions. This is the product.
2. **TSP Test Case (C)** — first application. Evolve a heuristic that beats LKH-2 on TSPLIB benchmarks.
3. **LKH-2 Baseline (C)** — original LKH-2 compiled and benchmarked as ground truth.

---

## Architecture

```
┌─────────────────────────────────────────────────┐
│                 orchestrator.py                   │
│  Launches sessions, manages worktrees,           │
│  passes messages, tracks results.tsv,            │
│  enforces stopping conditions                    │
├─────────────────────────────────────────────────┤
│  Strategist Session (1)  │  Researcher Sessions (N)  │
│  Coding agent pointed at │  Coding agents pointed at  │
│  strategist.md           │  researcher.md             │
│  Works in main worktree  │  Each in own git worktree  │
└─────────────────────────────────────────────────┘
```

### What the orchestrator does (Python)

- Launches coding agent sessions (one strategist, N researchers)
- Creates and manages git worktrees (one per researcher)
- Reads `state/results.tsv` to track progress and check stopping conditions
- Sends messages between sessions (strategist assignments → researchers)
- Enforces timeouts and stopping conditions
- Handles graceful shutdown (SIGINT/SIGTERM)

### What the orchestrator does NOT do

- Make LLM API calls (the coding agent does this)
- Edit source files (the coding agent does this)
- Parse or understand code (the coding agent does this)
- Run builds or benchmarks (the coding agent does this via bash)
- Handle build errors (the coding agent does this)
- Search the web (the coding agent does this)

### What ships with AlgoForge

```
algoforge/
├── orchestrator.py        # launches and manages agent sessions
├── cli.py                 # CLI entry point
├── config.py              # config loading and validation
├── eval.sh                # benchmark runner script (deterministic, no LLM)
├── prompts/
│   ├── strategist.md      # instructions for the strategist session
│   └── researcher.md      # instructions for each researcher session
└── config.yaml            # project configuration template
```

The prompts are the AlgoForge equivalent of AutoResearch's `program.md`. They define the agent's behavior. The orchestrator is the only real infrastructure code.

---

## Agent Types

Two types. Both are coding agent sessions pointed at different instruction files.

### Strategist (1 session)

A coding agent session (e.g., Claude Code) pointed at `strategist.md`. The strategist has full access to the coding agent's native capabilities: file read/edit, bash, git, and web search.

Responsibilities:

- **Research** — web search to understand the target algorithm, its domain, known limitations, and competing approaches. Can also discover and download seed code if not provided.
- **Initialize** — analyze seed codebase, decompose into modules, run baseline benchmarks
- **Assign** — write assignment files that researchers pick up
- **Compose** — merge best module branches, evaluate the combined build
- **Reprioritize** — shift researcher assignments based on evidence
- **Resolve conflicts** — handle git merge conflicts during composition. Only if resolution fails, fall back to cross-pollination mode.
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

### Researcher (N configurable sessions)

Each researcher is a separate coding agent session pointed at `researcher.md`, running in its own git worktree. The coding agent natively handles file editing, build errors, git operations — the researcher prompt just tells it *what* to do.

The researcher loop (defined in `researcher.md`):

1. Read the assignment file (`state/assignments/r<id>.yaml`)
2. Read the module source code
3. Read recent experiment history from `state/results.tsv`
4. Hypothesize an improvement
5. Edit the code
6. `git commit`
7. Build: run `make` — if it fails, read errors and fix (up to 3 retries)
8. Evaluate: run `eval.sh` — collect metrics
9. Compare to current best:
   - Better → keep the commit, append `keep` to results.tsv
   - Worse → `git reset --hard HEAD~1`, append `discard` to results.tsv
10. Repeat from step 3 until assignment file changes or max_iterations reached

The researcher prompt includes the NEVER STOP instruction (like AutoResearch): loop indefinitely until interrupted.

---

## Operating Modes

### Evolve Mode

Seed code exists or is discovered. The strategist decomposes it into modules and researchers improve them. Used for the TSP/LKH-2 test case.

If `seed_path` is not provided in the config, the strategist uses web search to find the best available open-source implementation for the problem domain, downloads it, and uses it as the seed.

### Generate Mode

No seed code. The strategist defines the problem specification and module interfaces from the config. Researchers generate implementations from scratch, guided by the strategist's domain knowledge.

In generate mode:
- The strategist creates module files with interface stubs (function signatures, expected inputs/outputs)
- Researchers implement the module internals from scratch
- The first few iterations focus on producing code that compiles and produces valid output (correctness before optimization)
- Once a working baseline exists, the normal evolve loop takes over

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

Each researcher session operates in its own `git worktree`. This is required because multiple sessions cannot share a single working directory.

On initialization:
- The orchestrator creates one worktree per researcher: `git worktree add .worktrees/r<id> module/<name>`
- Each researcher session works exclusively in its worktree
- The strategist session operates in the main working directory

Worktrees are created/destroyed by the orchestrator as researchers are assigned/reassigned.

### Project Directory

```
project/
├── config.yaml              # project configuration
├── seed/                    # original code (read-only, tagged in git)
├── eval.sh                  # benchmark runner script
├── state/                   # shared state (outside git)
│   ├── results.tsv          # single flat experiment log (append-only)
│   ├── strategist_log.tsv   # strategist decisions
│   └── assignments/         # current assignments per researcher
│       ├── r1.yaml
│       ├── r2.yaml
│       └── ...
├── prompts/                 # agent instruction files
│   ├── strategist.md
│   └── researcher.md
├── benchmarks/              # benchmark instances (e.g., TSPLIB .tsp files)
└── .worktrees/              # git worktrees (one per researcher)
    ├── r1/
    ├── r2/
    └── ...
```

### Communication via Filesystem

Agents communicate through the shared `state/` directory — no queues, no IPC, no custom protocol.

**Strategist → Researcher:**
- Writes `state/assignments/r<id>.yaml` with module name, files, objective, constraints, and context
- The researcher polls this file for changes

**Researcher → Strategist:**
- Appends to `state/results.tsv` (with file locking via `fcntl.flock`)
- The strategist polls this file to monitor progress

**Orchestrator → All:**
- Writes `state/shutdown` flag file to signal graceful stop
- All sessions check for this file periodically

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

1. **Shared headers are owned by the strategist**, not any researcher. If a researcher needs a header change, it proposes the change to the strategist (via a note in results.tsv), who applies it to `main` and propagates to all worktrees.
2. **Function signatures at module boundaries are frozen by default**. A researcher can change internals freely but must not change the signature of functions called by other modules. If a signature change is necessary, the researcher flags it to the strategist.
3. **The strategist tracks inter-module dependencies** during initialization by analyzing `#include` directives and function call graphs. This informs module decomposition — tightly coupled files go in the same module.

---

## Prompts

AlgoForge ships with **domain-agnostic default prompts** for both strategist and researcher. These are the equivalent of AutoResearch's `program.md`. The domain knowledge comes from:
- The strategist's web search (papers, techniques, known results)
- The seed codebase itself (the coding agent reads the code)
- The config (metric definition, benchmarks)
- Accumulated experiment history

Users can optionally provide a `domain_context` file with additional hints, but it is not required.

### Agent Model Configuration

AlgoForge does not hardcode a specific agent model. The model is configured by the coding tool used to run each session:

- **Claude Code**: `claude --model opus`, `/model sonnet`, or `ANTHROPIC_MODEL` env var
- **Codex**: configured via its own settings
- **Other tools**: configured via their respective mechanisms

The orchestrator launches sessions using the coding tool's CLI. The config specifies which tool and any model flags:

```yaml
agents:
  tool: "claude"                         # coding tool CLI command
  strategist:
    model_flags: "--model opus"          # passed to the tool on launch
  researchers:
    count: 4
    model_flags: "--model sonnet"        # passed to the tool on launch
```

This means AlgoForge works with any coding agent that has a CLI — no OpenRouter, no API key management, no model abstraction layer.

---

## Project Configuration

```yaml
project:
  name: "tsp-heuristic"
  mode: "evolve"                        # evolve | generate
  seed_path: "./seeds/lkh2/"            # optional — strategist can discover and download if omitted
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
  command: "make -j4"                   # incremental build. Use "make clean && make -j4" if Makefile deps are unreliable
  binary: "./LKH"                       # relative to worktree root

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
  tool: "claude"                        # coding tool CLI command
  strategist:
    model_flags: "--model opus"
  researchers:
    count: 4
    model_flags: "--model sonnet"
    max_iterations_per_assignment: 20

timeouts:
  build: 30                             # seconds for compilation
  eval_per_instance: 30                 # seconds per benchmark instance per run

stopping_conditions:
  max_total_iterations: 500
  max_hours: 24
  target_improvement: 0.5              # stop if we beat baseline by X% (absolute reduction in gap)
  stagnation_window: 50                # stop if no improvement in last N iterations
```

The module decomposition in config is a starting hint. The strategist can refine it after analyzing the codebase — split modules further, merge them, change file assignments.

---

## Strategist Lifecycle

```
Phase 1: INITIALIZATION
├── Load project config
├── Web search: research the target domain, algorithm, known weaknesses
├── If seed_path provided: analyze seed code
├── If seed_path omitted: web search to find and download best available implementation
├── Decompose codebase into modules (evolve mode) or define interfaces (generate mode)
├── Run baseline evaluation (compile + benchmark unmodified code)
└── Create initial module priority ranking

Phase 2: RESEARCH (main loop)
├── Write assignment files for researchers
├── Monitor researcher progress (poll state/results.tsv)
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
  target_improvement: 0.5           # stop if baseline beaten by X% (absolute)
  stagnation_window: 50             # stop if no improvement in last N iterations
```

The orchestrator checks these by polling `state/results.tsv`. When any condition triggers, it writes `state/shutdown` and waits for all sessions to finish their current iteration. The strategist then enters report mode.

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
algoforge status                                          # check progress (reads state/)
algoforge stop                                            # graceful stop → report
algoforge report                                          # generate report from completed run
```

## Claude Code Plugin

Thin wrapper over the CLI:

```
/algoforge-init     → algoforge init
/algoforge-start    → algoforge run (background)
/algoforge-status   → reads state/results.tsv + strategist_log.tsv, summarizes
/algoforge-stop     → sends stop signal
/algoforge-report   → algoforge report
```

The plugin adds interactive mode (v2): user can chat with the strategist mid-run to ask about decisions, suggest directions, or override priorities.

---

## What We Deleted (vs. previous spec)

The following are no longer part of AlgoForge because the coding agent handles them natively:

- ~~`models.py` (OpenRouter client)~~ → the coding tool's built-in LLM
- ~~`researcher.py` (edit/compile/eval loop)~~ → the coding agent follows `researcher.md`
- ~~`strategist.py` (agent logic)~~ → the coding agent follows `strategist.md`
- ~~`git_ops.py` (git operations)~~ → the coding agent runs git commands
- ~~Search/replace edit application~~ → the coding agent's native Edit function
- ~~Error handling for builds~~ → the coding agent reads errors and fixes them
- ~~Web search client~~ → the coding agent has web search
- ~~LLM interaction protocol~~ → the coding tool handles prompt construction, context management, token budgets
- ~~Concurrency model (asyncio, queues)~~ → each session is a separate process, communication via filesystem
- ~~OpenRouter / model abstraction~~ → model configured by the coding tool

---

## TSP Test Case: Setup Steps

1. Download LKH-2 source from Helsgaun's site (or let the strategist find it)
2. Compile and verify it runs on the target machine
3. Download TSPLIB benchmark instances
4. Run LKH-2 against all benchmark tiers (small/medium/large)
5. Record baseline results
6. Configure algoforge project with LKH-2 as seed
7. `algoforge run config.yaml`
