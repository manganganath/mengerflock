# AlgoForge

A hierarchical multi-agent system that evolves algorithms through autonomous experimentation.

Give AlgoForge a codebase, a build step, and a benchmark — it will coordinate a team of AI coding agents to systematically improve the code's performance. The strategist researches the domain, decomposes the problem, and directs parallel researchers who each evolve a piece of the codebase in a tight loop: hypothesize, implement, build, evaluate, keep or revert.

## Architecture

```
                    Orchestrator
           (launches tmux sessions, manages state)
                   /          \
          Strategist          Researchers (N)
     (research PI, web       (each in own git worktree,
      search, compose,        evolving assigned module)
      reassign, report)
```

The orchestrator is a thin Python layer that launches a tmux session with one window per agent. The real work happens in the coding agents (Claude Code, Codex, etc.) — each pointed at a markdown instruction file.

**Strategist** — the research PI. Analyzes the codebase, researches the domain via web search, decomposes the code into modules, assigns work, periodically composes the best modules into a combined build, reassigns researchers based on evidence, and writes the final report.

**Researchers** — N parallel workers. Each runs autonomously in its own git worktree, evolving its assigned module. The loop: read the code, form a hypothesis, edit, commit, build, benchmark, keep or revert. Indefinitely, until stopped.

## What Can AlgoForge Evolve?

Any codebase where you can compile, run against benchmarks, and get a number back. The requirements are simple: code + build step + measurable metric.

| Domain | Examples |
|---|---|
| **Combinatorial Optimization** | Routing heuristics, vehicle routing, graph coloring, bin packing, scheduling |
| **Search & Solvers** | SAT solvers, constraint satisfaction, branch-and-bound, local search frameworks |
| **Numerical Computing** | Matrix multiplication kernels, sorting algorithms, compression, signal processing |
| **ML Training** | Neural network training loops, optimizer implementations, data augmentation |
| **Compilers** | Optimization passes, code generation heuristics, register allocation |

The domain-agnostic design means AlgoForge doesn't need to be pre-configured for any specific problem type. The strategist researches the domain autonomously via web search.

## User Guide

### Prerequisites

- Python 3.11+
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) (or another coding agent with a CLI)
- tmux (`brew install tmux`)
- Git

### Step 1: Install AlgoForge

```bash
git clone https://github.com/manganganath/AlgoForge.git
cd AlgoForge
pip install -e .
```

### Step 2: Prepare Your Project

Create a project directory with:
- Your seed codebase (the algorithm you want to improve)
- Benchmark instances (holdout set for final evaluation)
- A `config.yaml` describing the project

```
my-project/
├── config.yaml
├── seed/               # your algorithm's source code
├── datasets/
│   └── holdout/        # established benchmark instances
└── eval.sh             # script that runs binary on one instance, outputs a number
```

### Step 3: Write config.yaml

```yaml
project:
  name: "my-algorithm"
  mode: "evolve"            # evolve (from seed) or generate (from scratch)
  seed_path: "./seed/"
  language: "c"             # language of the seed codebase

modules:                    # the strategist can refine these after analyzing the code
  - name: "core_logic"
    files: ["src/core.c"]
    description: "Main algorithm logic"
  - name: "heuristics"
    files: ["src/heuristic.c"]
    description: "Heuristic evaluation functions"

build:
  command: "make -j4"
  binary: "./solver"

benchmarks:
  small: ["datasets/holdout/small_*.txt"]
  medium: ["datasets/holdout/med_*.txt"]
  large: ["datasets/holdout/large_*.txt"]

evaluation:
  metric: "gap_to_optimal"
  runs_per_instance: 5
  random_seeds: [42, 123, 456, 789, 1024]

agents:
  tool: "claude"                        # coding tool CLI command
  strategist:
    model_flags: "--model opus"         # stronger model for research PI
  researchers:
    count: 3                            # number of parallel researchers
    model_flags: "--model sonnet"       # faster model for iteration
    max_iterations_per_assignment: 20

stopping_conditions:
  max_total_iterations: 500
  max_hours: 24
  stagnation_window: 50
```

### Step 4: Initialize and Run

```bash
cd my-project

# Initialize (creates state directory, git branches)
algoforge init --config config.yaml

# Run (launches tmux session with strategist + N researchers)
algoforge run config.yaml
```

### Step 5: Monitor

```bash
# Attach to the tmux session to watch agents work
tmux attach -t algoforge

# Switch between windows:
#   Ctrl+B then 1  → strategist
#   Ctrl+B then 2  → researcher r1
#   Ctrl+B then 3  → researcher r2
#   Ctrl+B then n  → next window
#   Ctrl+B then d  → detach (agents keep running)

# Or check progress from any terminal
algoforge status
```

### Step 6: Stop and Report

```bash
# Graceful stop — finishes current iterations, strategist writes report
algoforge stop

# Or generate report from a completed/stopped run
algoforge report
```

The strategist writes a comprehensive report to `report/report.md` including what was tried, what worked, benchmark comparisons, and a description of the evolved algorithm.

### Tips

- **Start small.** Use 2-3 researchers and small benchmarks first. Scale up once you see the loop working.
- **Let it run overnight.** Each researcher can do ~10-12 experiments per hour. An overnight run gives you 80-100 experiments per researcher.
- **Check `state/results.tsv`** for a quick view of all experiments across all researchers.
- **The strategist is the bottleneck.** It needs to compose, evaluate, and reassign. If researchers are idle, check the strategist window.
- **Seed code matters.** Start from the best available implementation. The agents evolve from there — they don't invent from scratch (in evolve mode).

## How It Runs

AlgoForge creates a tmux session called `algoforge` with one window per agent:

```
Window 0: strategist  — research, decompose, assign, compose, report
Window 1: r1          — evolving module A in its own git worktree
Window 2: r2          — evolving module B in its own git worktree
Window 3: r3          — evolving module C in its own git worktree
```

Each window runs an interactive coding agent session. Agents communicate through a shared `state/` directory:
- `state/results.tsv` — experiment log (researchers append, strategist reads)
- `state/assignments/` — work assignments (strategist writes, researchers read)
- `state/strategist_log.tsv` — strategist decisions and observations
- `state/shutdown` — flag file to signal graceful stop

Symlinks into each worktree give researchers access to shared resources (state/, eval.sh, datasets/) using local paths.

## Evaluation Strategy

AlgoForge uses a train/validation/holdout split to ensure improvements generalize:

| Dataset | Source | Used by | Purpose |
|---|---|---|---|
| **Train** | Synthetic (generated by strategist) | Researchers | Iterate, keep/discard decisions |
| **Validation** | Synthetic (separate set) | Strategist | Composition evaluation |
| **Holdout** | Established benchmarks | Report phase only | Final evaluation, never seen during development |

The strategist inspects the holdout format and generates synthetic train/validation instances in the same format, so the target binary can consume them without modification.

## Configuration

```yaml
project:
  name: "my-algorithm"
  mode: "evolve"            # evolve (from seed) or generate (from scratch)
  seed_path: "./seed/"
  language: "c"

modules:
  - name: "core_logic"
    files: ["src/core.c"]
    description: "Main algorithm logic"

build:
  command: "make -j4"
  binary: "./solver"

benchmarks:
  small: ["bench/small1.txt"]
  medium: ["bench/med1.txt"]
  large: ["bench/large1.txt"]

evaluation:
  metric: "gap_to_optimal"
  runs_per_instance: 5
  random_seeds: [42, 123, 456, 789, 1024]

agents:
  tool: "claude"
  strategist:
    model_flags: "--model opus"
  researchers:
    count: 4
    model_flags: "--model sonnet"
    max_iterations_per_assignment: 20

stopping_conditions:
  max_total_iterations: 500
  max_hours: 24
  stagnation_window: 50
```

## Evolution Strategy

**Primary: Decomposed Module Evolution** — the strategist splits the codebase into modules. Each researcher evolves one module on a dedicated git branch. The strategist incrementally composes modules one at a time, evaluating after each merge to detect conflicts (e.g., one module speeds up trials while another adds preprocessing that cancels the speedup).

**Fallback: Cross-Pollination** — when module composition fails due to tight coupling, researchers fork the full codebase and evolve holistically. This is a last resort, triggered only after the strategist fails to resolve merge conflicts.

**Stagnation Handling** — if a researcher has 3+ consecutive failures, the strategist escalates: reframe the objective, widen file scope, switch to cross-pollination mode, or reassign to a different module.

## Design Principles

- **Agents are coding tool sessions**, not custom LLM infrastructure. AlgoForge doesn't make API calls — it launches Claude Code / Codex sessions pointed at instruction files.
- **Git is the state manager.** Worktrees for isolation, branches for versioning, tags for milestones.
- **Filesystem for communication.** Agents read/write a shared `state/` directory. No queues, no IPC.
- **The strategist has web search.** It can autonomously research unfamiliar domains, find papers, and discover seed code.
- **Train/validation/holdout split.** Researchers never see the holdout benchmark. Results are credible.

## Project Structure

```
algoforge/
├── src/algoforge/
│   ├── cli.py              # CLI entry point
│   ├── config.py           # config loading and validation
│   ├── state.py            # results.tsv, assignments, shutdown
│   ├── worktree.py         # git worktree management
│   ├── orchestrator.py     # tmux session launching and monitoring
│   └── eval.sh             # benchmark evaluation script
├── prompts/
│   ├── strategist.md       # strategist agent instructions
│   └── researcher.md       # researcher agent instructions
├── examples/               # example project configs
└── tests/
```
