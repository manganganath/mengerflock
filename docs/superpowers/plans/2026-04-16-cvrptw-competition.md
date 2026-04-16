# CVRPTW Competition Preparation — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prepare MengerFlock to compete in the GECCO 2026 ML4VRP CVRPTW track — config/prompt changes, template setup, and 2-page abstract by April 21.

**Architecture:** Two small config additions to MengerFlock (pre_check, training data sourcing), a CVRPTW experiment template with PyVRP seed, and a 2-page ACM sigconf abstract.

**Tech Stack:** Python (PyVRP), C++ (PyVRP backend, untouched), LaTeX (ACM sigconf), tectonic (PDF compilation)

**Spec:** `docs/superpowers/specs/2026-04-16-cvrptw-competition-design.md`

---

## Task 1: Add `pre_check` field to EvaluationConfig

**Files:**
- Modify: `src/mengerflock/config.py`
- Modify: `tests/test_config.py`

- [ ] **Step 1: Add test for pre_check field**

In `tests/test_config.py`, add:

```python
def test_pre_check_default_none(tmp_path):
    cfg = load_config(_write_config(tmp_path, MINIMAL_CONFIG))
    assert cfg.evaluation.pre_check is None

def test_pre_check_loaded(tmp_path):
    with_precheck = MINIMAL_CONFIG.replace(
        "  metric: gap_to_optimal",
        "  metric: gap_to_optimal\n  pre_check: \"python verify.py\""
    )
    cfg = load_config(_write_config(tmp_path, with_precheck))
    assert cfg.evaluation.pre_check == "python verify.py"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_config.py -v -k "pre_check"`
Expected: FAIL (no `pre_check` attribute)

- [ ] **Step 3: Add pre_check to EvaluationConfig dataclass**

In `src/mengerflock/config.py`, modify `EvaluationConfig`:

```python
@dataclasses.dataclass
class EvaluationConfig:
    metric: str
    progressive: bool = True
    runs_per_instance: int = 5
    random_seeds: list[int] = dataclasses.field(default_factory=lambda: [42, 123, 456, 789, 1024])
    pre_check: str | None = None
```

And in `load_config`, modify the evaluation parsing (around line 183):

```python
    evaluation = EvaluationConfig(
        metric=_require(eval_raw, "metric", "evaluation"),
        progressive=eval_raw.get("progressive", True),
        runs_per_instance=runs_per_instance,
        random_seeds=random_seeds,
        pre_check=eval_raw.get("pre_check"),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_config.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/mengerflock/config.py tests/test_config.py
git commit -m "feat(config): add optional pre_check field to evaluation"
```

---

## Task 2: Add training data sourcing fields to TrainingConfig

**Files:**
- Modify: `src/mengerflock/config.py`
- Modify: `tests/test_config.py`

- [ ] **Step 1: Add tests for new training fields**

In `tests/test_config.py`, add:

```python
def test_training_data_source_defaults(tmp_path):
    cfg = load_config(_write_config(tmp_path, MINIMAL_CONFIG))
    assert cfg.training.data_source is None
    assert cfg.training.split_source is None
    assert cfg.training.split_ratios is None
    assert cfg.training.stratify_by is None

def test_training_data_source_split(tmp_path):
    with_split = MINIMAL_CONFIG + """
training:
  data_source: "split"
  split_source: "datasets/all/"
  split_ratios: [0.6, 0.2, 0.2]
  stratify_by: "instance_type"
"""
    cfg = load_config(_write_config(tmp_path, with_split))
    assert cfg.training.data_source == "split"
    assert cfg.training.split_source == "datasets/all/"
    assert cfg.training.split_ratios == [0.6, 0.2, 0.2]
    assert cfg.training.stratify_by == "instance_type"

def test_training_split_ratios_must_sum_to_one(tmp_path):
    bad_ratios = MINIMAL_CONFIG + """
training:
  data_source: "split"
  split_source: "datasets/all/"
  split_ratios: [0.5, 0.2, 0.2]
"""
    with pytest.raises(ConfigError):
        load_config(_write_config(tmp_path, bad_ratios))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_config.py -v -k "training_data"`
Expected: FAIL

- [ ] **Step 3: Add fields to TrainingConfig and load_config**

In `src/mengerflock/config.py`, modify `TrainingConfig`:

```python
@dataclasses.dataclass
class TrainingConfig:
    train: str | None = None
    validation: str | None = None
    data_source: str | None = None        # "split" | "generate" | "download" | "manual"
    split_source: str | None = None       # directory to split (if data_source="split")
    split_ratios: list[float] | None = None  # [train, validation, holdout]
    stratify_by: str | None = None        # optional grouping key for stratified splits
```

Modify the training parsing in `load_config` (around line 191):

```python
    # Training (optional — strategist generates if missing)
    train_raw = raw.get("training", {})
    split_ratios = train_raw.get("split_ratios")
    if split_ratios is not None and abs(sum(split_ratios) - 1.0) > 0.01:
        raise ConfigError("training.split_ratios must sum to 1.0")
    training = TrainingConfig(
        train=train_raw.get("train"),
        validation=train_raw.get("validation"),
        data_source=train_raw.get("data_source"),
        split_source=train_raw.get("split_source"),
        split_ratios=split_ratios,
        stratify_by=train_raw.get("stratify_by"),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_config.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/mengerflock/config.py tests/test_config.py
git commit -m "feat(config): add training data sourcing fields (data_source, split_ratios, stratify_by)"
```

---

## Task 3: Update strategist prompt for data sourcing with split support

**Files:**
- Modify: `prompts/strategist.md`

- [ ] **Step 1: Update step 11 (Set up training and validation datasets)**

In `prompts/strategist.md`, replace step 11 content. After the existing data sourcing rules (ask user, present options), add guidance for when `data_source` is set in config:

```markdown
    - If `training.data_source` is set in config, use it as the default approach:
      - `"split"`: Read `training.split_source` for the corpus directory, `training.split_ratios` for ratios (default 60/20/20), and `training.stratify_by` for optional stratification. Confirm with the user: "Config suggests splitting `<split_source>` at <ratios> stratified by <stratify_by>. Proceed?" Then execute the split and populate `datasets/train/`, `datasets/validation/`, `datasets/holdout/`.
      - `"download"`: Ask the user for the URL or repository to download from.
      - `"generate"`: Generate synthetic instances matching the format of holdout files.
      - `"manual"`: Skip — the user will provide data later.
    - If `training.data_source` is NOT set, fall back to asking the user with no defaults.
```

- [ ] **Step 2: Verify the markdown reads correctly**

Read the file and confirm step numbering and formatting are intact.

- [ ] **Step 3: Commit**

```bash
git add prompts/strategist.md
git commit -m "feat(strategist): add data sourcing config support for split/generate/download/manual"
```

---

## Task 4: Update project-template config.yaml with new fields

**Files:**
- Modify: `project-template/config.yaml`

- [ ] **Step 1: Add the new fields to the template**

Add `pre_check` to evaluation (commented out) and the training data sourcing fields (commented out):

```yaml
evaluation:
  metric: "gap_to_optimal"
  runs_per_instance: 5
  random_seeds: [42, 123, 456, 789, 1024]
  # pre_check: "python scripts/verify.py"  # optional: runs before eval.sh

training:
  train: "../project-template/datasets/train/"
  validation: "../project-template/datasets/validation/"
  # data_source: "split"                    # "split" | "generate" | "download" | "manual"
  # split_source: "datasets/all/"
  # split_ratios: [0.6, 0.2, 0.2]
  # stratify_by: "instance_type"
```

- [ ] **Step 2: Commit**

```bash
git add project-template/config.yaml
git commit -m "feat(template): add pre_check and data sourcing fields to config template"
```

---

## Task 5: Clone PyVRP into original-seed

**Files:**
- Create: `projects/cvrptw/original-seed/` (git clone of PyVRP)

- [ ] **Step 1: Create the cvrptw project directory**

```bash
mkdir -p projects/cvrptw
```

- [ ] **Step 2: Clone PyVRP**

```bash
cd projects/cvrptw
git clone https://github.com/PyVRP/PyVRP.git original-seed
```

- [ ] **Step 3: Remove PyVRP's .git directory**

```bash
rm -rf projects/cvrptw/original-seed/.git
```

- [ ] **Step 4: Verify the clone contains the expected Python heuristic files**

```bash
ls projects/cvrptw/original-seed/pyvrp/search/
ls projects/cvrptw/original-seed/pyvrp/crossover/
ls projects/cvrptw/original-seed/pyvrp/diversity/
```

Expected: Python files in each directory.

- [ ] **Step 5: Verify PyVRP builds**

```bash
cd projects/cvrptw/original-seed
pip install -e . --quiet
python -c "import pyvrp; print(pyvrp.__version__)"
```

Expected: Version number printed, no errors.

Note: `projects/` is gitignored, so no commit needed.

---

## Task 6: Download CVRPTW datasets

**Files:**
- Create: `projects/cvrptw/datasets/all/` (Solomon + Homberger instances)

- [ ] **Step 1: Download Solomon 100-node CVRPTW instances**

```bash
mkdir -p projects/cvrptw/datasets/all
```

Download all Solomon CVRPTW instances (C1, C2, R1, R2, RC1, RC2 types, 100 customers each) from the standard repository. Check CVRPLIB or the ML4VRP GitHub for the exact download source.

- [ ] **Step 2: Download Homberger & Gehring 200-node and 400-node instances**

Download from the same source. These are extensions of Solomon with larger instance sizes.

- [ ] **Step 3: Verify instance count and types**

```bash
ls projects/cvrptw/datasets/all/ | wc -l
ls projects/cvrptw/datasets/all/ | head -20
```

Expected: Solomon (56 instances) + Homberger 200-node + Homberger 400-node instances. Each filename should indicate its type (C1, C2, R1, R2, RC1, RC2).

- [ ] **Step 4: Download the official ML4VRP evaluator**

```bash
git clone https://github.com/ML4VRP/ML4VRP2024.git /tmp/ml4vrp-evaluator
```

Copy the evaluator script to `projects/cvrptw/scripts/` for local scoring verification.

---

## Task 7: Stratified split of datasets

**Files:**
- Create: `projects/cvrptw/datasets/train/`
- Create: `projects/cvrptw/datasets/validation/`
- Create: `projects/cvrptw/datasets/holdout/`

- [ ] **Step 1: Write a split script**

Create `projects/cvrptw/scripts/split_datasets.py`:

```python
"""Stratified split of CVRPTW instances into train/validation/holdout."""
import os
import shutil
import random
from collections import defaultdict
from pathlib import Path

def get_instance_type(filename):
    """Extract type prefix (C1, C2, R1, R2, RC1, RC2) from filename."""
    name = Path(filename).stem.upper()
    for prefix in ["RC1", "RC2", "C1", "C2", "R1", "R2"]:
        if name.startswith(prefix):
            return prefix
    return "OTHER"

def split(source_dir, output_dir, ratios=(0.6, 0.2, 0.2), seed=42):
    random.seed(seed)
    source = Path(source_dir)
    instances = sorted(f.name for f in source.iterdir() if f.is_file())

    # Group by type
    by_type = defaultdict(list)
    for inst in instances:
        by_type[get_instance_type(inst)].append(inst)

    splits = {"train": [], "validation": [], "holdout": []}
    for type_name, type_instances in sorted(by_type.items()):
        random.shuffle(type_instances)
        n = len(type_instances)
        n_train = max(1, round(n * ratios[0]))
        n_val = max(1, round(n * ratios[1]))
        splits["train"].extend(type_instances[:n_train])
        splits["validation"].extend(type_instances[n_train:n_train + n_val])
        splits["holdout"].extend(type_instances[n_train + n_val:])

    out = Path(output_dir)
    for split_name, files in splits.items():
        split_dir = out / split_name
        split_dir.mkdir(parents=True, exist_ok=True)
        for f in files:
            shutil.copy2(source / f, split_dir / f)
        print(f"{split_name}: {len(files)} instances")

if __name__ == "__main__":
    split("datasets/all", "datasets")
```

- [ ] **Step 2: Run the split**

```bash
cd projects/cvrptw
python scripts/split_datasets.py
```

Expected: Printed counts for train/validation/holdout with balanced type distribution.

- [ ] **Step 3: Verify stratification**

```bash
ls datasets/train/ | grep -i "^C1" | wc -l
ls datasets/train/ | grep -i "^R1" | wc -l
ls datasets/train/ | grep -i "^RC1" | wc -l
```

Expected: Each type has roughly proportional representation.

---

## Task 8: Create eval.sh

**Files:**
- Create: `projects/cvrptw/eval.sh`

- [ ] **Step 1: Write eval.sh**

```bash
#!/usr/bin/env bash
# Evaluate PyVRP on a single CVRPTW instance.
# Usage: ./eval.sh <binary> <instance> <seed> <timeout>
# Outputs: single number (1000*NV + TD) to stdout
# Outputs: NV and TD to stderr for visibility

set -euo pipefail

BINARY="$1"
INSTANCE="$2"
SEED="$3"
TIMEOUT="$4"

# Run solver with timeout
RESULT=$(timeout "${TIMEOUT}s" $BINARY "$INSTANCE" --seed "$SEED" 2>/dev/null) || {
    echo "FAIL: timeout or crash" >&2
    exit 1
}

# Parse NV and TD from solver output
NV=$(echo "$RESULT" | grep -i "routes\|vehicles" | head -1 | grep -oE '[0-9]+')
TD=$(echo "$RESULT" | grep -i "distance\|cost" | head -1 | grep -oE '[0-9]+(\.[0-9]+)?')

if [ -z "$NV" ] || [ -z "$TD" ]; then
    echo "FAIL: could not parse NV or TD from output" >&2
    exit 1
fi

echo "NV=$NV TD=$TD" >&2
echo "$NV $TD" | awk '{printf "%.3f\n", 1000 * $1 + $2}'
```

Note: The exact parsing of PyVRP's output format will need adjustment after testing with the actual solver. This is a starting skeleton.

- [ ] **Step 2: Make it executable**

```bash
chmod +x projects/cvrptw/eval.sh
```

- [ ] **Step 3: Test with a single instance**

```bash
cd projects/cvrptw
./eval.sh "python -m pyvrp" datasets/train/<some_instance>.txt 42 60
```

Expected: A single number on stdout, NV and TD on stderr.

- [ ] **Step 4: Fix parsing as needed based on actual PyVRP output format**

Read PyVRP docs or run it manually to understand the output format, then adjust the grep/awk patterns.

---

## Task 9: Create verify_solution.py (pre-check)

**Files:**
- Create: `projects/cvrptw/scripts/verify_solution.py`

- [ ] **Step 1: Write the verification script**

```python
"""Pre-check: verify a CVRPTW solution is feasible.
Checks: all customers visited exactly once, capacity, time windows, depot return.
Exit 0 = feasible, exit 1 = infeasible.
"""
import sys

def verify(instance_path, solution_path):
    """Verify solution feasibility against instance constraints."""
    # TODO: Implement after understanding PyVRP's solution output format
    # For now, check that the solution file exists and is non-empty
    from pathlib import Path
    sol = Path(solution_path)
    if not sol.exists() or sol.stat().st_size == 0:
        print("FAIL: solution file missing or empty", file=sys.stderr)
        return False
    return True

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <instance> <solution>", file=sys.stderr)
        sys.exit(1)
    if not verify(sys.argv[1], sys.argv[2]):
        sys.exit(1)
```

Note: Full constraint checking will be implemented after understanding PyVRP's instance/solution formats. The skeleton ensures the pre_check pipeline works end-to-end.

- [ ] **Step 2: Test**

```bash
python projects/cvrptw/scripts/verify_solution.py /dev/null /dev/null
echo $?
```

Expected: Exit code 1 (empty/missing solution).

---

## Task 10: Create config.yaml for CVRPTW template

**Files:**
- Create: `projects/cvrptw/config.yaml`

- [ ] **Step 1: Write config.yaml**

```yaml
project:
  name: "pyvrp"
  seed_path: "./seed/"
  original_seed_path: "./original-seed/"
  language: "python"
  paper: "./paper.md"

modules:
  - name: "search"
    files: ["pyvrp/search/*.py"]
    description: "Local search and ALNS destroy/repair operators"
  - name: "crossover"
    files: ["pyvrp/crossover/*.py"]
    description: "Genetic crossover mechanisms"
  - name: "diversity"
    files: ["pyvrp/diversity/*.py"]
    description: "Population penalty coefficients and diversity management"

build:
  command: "pip install -e . --quiet"
  binary: "python -m pyvrp"

benchmarks:
  small: ["datasets/holdout/C1*", "datasets/holdout/C2*", "datasets/holdout/R1*", "datasets/holdout/R2*", "datasets/holdout/RC1*", "datasets/holdout/RC2*"]

training:
  train: "datasets/train/"
  validation: "datasets/validation/"
  data_source: "split"
  split_source: "datasets/all/"
  split_ratios: [0.6, 0.2, 0.2]
  stratify_by: "instance_type"

evaluation:
  metric: "weighted_objective"
  pre_check: "python scripts/verify_solution.py"
  runs_per_instance: 5
  random_seeds: [42, 123, 456, 789, 1024]

agents:
  tool: "claude"
  strategist:
    model_flags: "--model opus"
  researchers:
    model_flags: "--model sonnet"
    max_iterations_per_assignment: 20
  wildcard:
    model_flags: "--model opus"

stopping_conditions:
  max_total_iterations: 500
  max_hours: 24
  stagnation_window: 50
```

- [ ] **Step 2: Verify config loads**

```bash
python -c "from mengerflock.config import load_config; c = load_config('projects/cvrptw/config.yaml'); print(c.project.name, c.evaluation.pre_check)"
```

Expected: `pyvrp python scripts/verify_solution.py`

---

## Task 11: Write paper.md

**Files:**
- Create: `projects/cvrptw/paper.md`

- [ ] **Step 1: Research PyVRP architecture**

Read the PyVRP source code (cloned in Task 5) and the PyVRP paper. Focus on:
- Python vs C++ boundary
- ALNS operator structure (destroy/repair)
- Crossover operator structure
- Population diversity/penalty management
- PyVRP+ improvements (from the arxiv paper)

- [ ] **Step 2: Write paper.md**

Contents:
1. **PyVRP Architecture** — C++ core (distance matrices, constraint checking) vs Python heuristic layer (search, crossover, diversity)
2. **Key Components** — ALNS destroy/repair operators, crossover mechanisms, penalty coefficients, population management
3. **Known Improvement Directions** — From PyVRP+ paper: evolved parent selection, adaptive stratified diversity, instance-adaptive parameters
4. **Module Decomposition** — Recommended researcher assignments: search (ALNS), crossover (genetic operators), diversity (penalty management)
5. **Competition Scoring Note** — F1 scoring means robustness across instance families (C, R, RC) matters more than peak performance on a few instances. Consistently top-8 across all instances beats 1st on half and 9th on the rest.

---

## Task 12: Run preliminary experiment (24h)

**Files:**
- Create: `projects/cvrptw-experiment-1/` (via `mengerflock new`)

- [ ] **Step 1: Create the experiment**

```bash
cd projects
python -m mengerflock.cli new cvrptw-experiment-1 --from cvrptw
```

- [ ] **Step 2: Start the experiment**

```bash
cd cvrptw-experiment-1
python -m mengerflock.cli run config.yaml
```

- [ ] **Step 3: Attach to tmux and approve Phase 1 plan**

```bash
tmux attach -t mengerflock
```

Approve the strategist's research plan when prompted.

- [ ] **Step 4: Let it run for ~24 hours**

Monitor with:
```bash
python -m mengerflock.cli status
```

- [ ] **Step 5: Stop and collect results**

```bash
python -m mengerflock.cli stop
```

Wait for Phase 3 to complete. Results will be in `report/`.

---

## Task 13: Write and submit 2-page GECCO abstract

**Files:**
- Create: `projects/cvrptw/abstract/abstract.tex`
- Create: `projects/cvrptw/abstract/abstract.pdf`

- [ ] **Step 1: Download ACM sigconf template**

Use the ACM Primary Article Template (sigconf) from Overleaf or ACM's website. Set up:

```bash
mkdir -p projects/cvrptw/abstract
```

- [ ] **Step 2: Write the abstract LaTeX**

Structure (2 pages max including references):

```latex
\documentclass[sigconf]{acmart}

\title{MengerFlock: Autonomous Multi-Agent Algorithm Evolution for Vehicle Routing}
\author{Nuwan Ganganath}
\email{manganganath@gmail.com}

\begin{abstract}
We present MengerFlock, an autonomous multi-agent system that evolves
metaheuristic components through LLM-driven code modification and
systematic evaluation. Applied to the Capacitated Vehicle Routing Problem
with Time Windows (CVRPTW), MengerFlock deploys parallel researcher agents
that independently hypothesize, implement, and validate modifications to
PyVRP's search operators, crossover mechanisms, and diversity management.
A strategist agent coordinates composition of successful modifications
with single-keep validation and regression gates. Preliminary results on
Solomon benchmark instances show [X]% improvement over baseline PyVRP.
\end{abstract}

% Section 1: Introduction (MengerFlock + why LLM code evolution for VRP)
% Section 2: Approach (three-phase lifecycle, regression gate, isolated testing)
% Section 3: Preliminary Results (table: baseline vs evolved on Solomon subset)
% Section 4: Conclusion
% References: PyVRP, PyVRP+, MengerFlock repo
```

- [ ] **Step 3: Fill in preliminary results from Task 12**

Insert actual numbers from the experiment into the results table.

- [ ] **Step 4: Compile**

```bash
cd projects/cvrptw/abstract
tectonic abstract.tex
```

- [ ] **Step 5: Verify PDF is 2 pages**

```bash
pdfinfo abstract.pdf | grep Pages
```

Expected: `Pages: 2`

- [ ] **Step 6: Submit**

Email to Rong.Qu@nottingham.ac.uk with:
- Subject: `[ML4VRP-Submission] MengerFlock`
- Attach: `abstract.pdf`
- Body: team name, algorithm name, leader, affiliation, track (CVRPTW)

**Deadline: April 21, 2026**

---

## Task 14: Update iteration-8-improvements.md

**Files:**
- Modify: `docs/iterations/iteration-8-improvements.md`

- [ ] **Step 1: Rewrite the document**

Replace current content with a domain-agnostic process doc covering only the two MengerFlock improvements:

1. Pre-check step in evaluation (`evaluation.pre_check` config field)
2. Training data sourcing config (`data_source`, `split_ratios`, `stratify_by` fields)

No mention of GECCO, ML4VRP, PyVRP, or VRP. Keep it in the same style as iteration-7-improvements.md (Before/After/Rationale/Configuration).

- [ ] **Step 2: Commit**

```bash
git add docs/iterations/iteration-8-improvements.md
git commit -m "docs: rewrite iteration-8 as domain-agnostic process improvements"
```
