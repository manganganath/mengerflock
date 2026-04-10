# AlgoForge — Iteration 1 Improvement Log

Issues and improvements identified during the first manual test run.

## Critical

### 1. Researchers not logging to results.tsv
All three researchers are running experiments and committing code, but none are appending results to `state/results.tsv`. This breaks the strategist's ability to monitor progress and compose modules.

**Root cause:** Path mismatch. `researcher.md` says `state/results.tsv` (relative), but researchers run in `.worktrees/r1/` where that path doesn't exist. The initial prompt said `../../state/` but the .md file says `state/` — conflicting instructions. The agents followed the .md file, couldn't find the file, and silently skipped logging.

**Fix options:**
- Use absolute paths in the prompt or a `paths.yaml` written into each worktree by the orchestrator
- Symlink `state/` into each worktree during setup
- Have `researcher.md` reference a `STATE_DIR` variable set by the launch command

### 2. eval.sh not macOS compatible
`timeout` command doesn't exist on macOS. `grep -oP` (Perl regex) is GNU-only. `mktemp` with custom suffixes (`.par`, `.tour`) fails on macOS. All three researchers independently discovered and worked around these issues, wasting their first iterations. **Fix eval.sh to work on macOS out of the box.**

### 3. Orchestrator can't launch interactive sessions
`subprocess.Popen(["claude", "-p", ...])` runs a single prompt and exits. Claude Code needs an interactive TTY for the autonomous loop. Options:
- Use `tmux`/`screen` to provide TTYs
- Use Claude Code SDK for programmatic session management
- Use `claude --resume` or similar persistent session features

## Important

### 4. Researchers wrote their own eval loops instead of using eval.sh
Because eval.sh was broken, all researchers wrote custom bash loops to run LKH and parse output. This means each researcher has slightly different evaluation methodology. The eval script should be robust enough that researchers use it directly.

### 5. Config paths don't match actual file layout
`config.yaml` references `./seeds/lkh2/` and `benchmarks/tsplib/` but actual paths are `LKH-2/` and `datasets/`. Config wasn't used by the agents — they figured out paths on their own. Either fix the config or make researchers read it.

### 6. Strategist exited after Phase 1
Using `-p` flag caused the strategist to complete initialization and exit. It needs to stay running for Phase 2 (monitoring, composition, reassignment). The manual workaround was to restart in interactive mode.

### 7. No baseline recorded in results.tsv
The first entry in results.tsv should be the baseline (unmodified LKH-2) so all subsequent experiments have something to compare against. Currently the researchers compute baselines locally but don't log them.

## Nice to Have

### 8. Researchers running baselines redundantly
All three researchers + the strategist independently ran the same baseline benchmarks (4x the work). The strategist should run the baseline once during initialization and write it to a shared file.

### 9. No progress visibility without terminal access
The only way to see what's happening is to look at each terminal. `algoforge status` should work by reading results.tsv, but since nothing is logged there, it shows nothing. Need a lightweight monitoring approach even during manual runs.

### 10. Git worktree creation requires knowing the main branch name
`git worktree add .worktrees/r1 -b module/move_operators main` failed because the branch was `main` but hadn't been committed yet, or was named differently. The orchestrator/setup script should handle this.

### 11. Researcher prompt path references are fragile
Researchers need to reference `../../state/`, `../../eval.sh` etc. which breaks if the worktree is at a different depth. Should use absolute paths or a well-known location.

### 12. No cost tracking
No visibility into how many API tokens/dollars each researcher is consuming. Important for long runs.
