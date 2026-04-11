from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import click

from mengerflock.config import load_config
from mengerflock.orchestrator import Orchestrator, init_project
from mengerflock.state import (
    is_shutdown_requested,
    read_baseline_holdout,
    read_results,
    read_strategist_log,
    write_shutdown_flag,
)


@click.group()
def main() -> None:
    """MengerFlock — automated algorithm discovery through multi-agent evolution."""
    pass


@main.command()
@click.option("--seed", type=click.Path(exists=True), help="Path to seed codebase")
@click.option("--config", "config_path", required=True, type=click.Path(exists=True))
def init(seed: str | None, config_path: str) -> None:
    """Initialize a new MengerFlock project."""
    config = load_config(config_path)
    project_dir = Path.cwd()

    if seed:
        config.project.seed_path = seed

    init_project(project_dir, config)
    click.echo(f"Project initialized: {config.project.name}")
    click.echo(f"State directory: {project_dir / 'state'}")


@main.command()
@click.argument("config_path", type=click.Path(exists=True))
def run(config_path: str) -> None:
    """Run the MengerFlock experiment."""
    config = load_config(config_path)
    project_dir = Path.cwd()

    if not (project_dir / "state").exists():
        init_project(project_dir, config)

    orchestrator = Orchestrator(project_dir, config)
    click.echo(f"Starting MengerFlock: {config.agents.researchers.count} researchers")
    orchestrator.run()


@main.command()
def status() -> None:
    """Show current experiment progress."""
    state_dir = Path.cwd() / "state"
    if not state_dir.exists():
        click.echo("No active project. Run 'mengerflock init' first.")
        return

    results = read_results(state_dir)
    keeps = [r for r in results if r["status"] == "keep"]
    discards = [r for r in results if r["status"] == "discard"]
    crashes = [r for r in results if r["status"] == "crash"]

    click.echo(f"Total experiments: {len(results)}")
    click.echo(f"  Keep: {len(keeps)}")
    click.echo(f"  Discard: {len(discards)}")
    click.echo(f"  Crash: {len(crashes)}")

    if keeps:
        best = min(keeps, key=lambda r: float(r["metric_avg"]))
        click.echo(f"Best metric_avg: {best['metric_avg']} ({best['module']}, {best['commit']})")

    if is_shutdown_requested(state_dir):
        click.echo("Status: SHUTTING DOWN")
    else:
        click.echo("Status: RUNNING")


@main.command()
def stop() -> None:
    """Gracefully stop the experiment."""
    state_dir = Path.cwd() / "state"
    if not state_dir.exists():
        click.echo("No active project.")
        return

    write_shutdown_flag(state_dir)
    click.echo("Shutdown signal sent. Sessions will finish current iteration and stop.")


@main.command()
@click.option("--force", is_flag=True, help="Skip confirmation")
def clean(force: bool) -> None:
    """Remove all experiment state (state/, .worktrees/, report/, experiment branches)."""
    import shutil

    project_dir = Path.cwd()

    if not force:
        click.confirm("This will delete state/, .worktrees/, report/, and experiment branches. Continue?", abort=True)

    for d in ["state", ".worktrees", "report"]:
        p = project_dir / d
        if p.exists():
            shutil.rmtree(p)
            click.echo(f"Removed {d}/")

    # Remove experiment branches
    from mengerflock.worktree import _git
    result = _git(project_dir, "branch", "--list", check=False)
    if result.returncode == 0:
        for line in result.stdout.splitlines():
            branch = line.strip().lstrip("* ")
            if branch.startswith(("wildcard/", "researcher/", "crosspollin/")):
                _git(project_dir, "branch", "-D", branch, check=False)
                click.echo(f"Deleted branch {branch}")

    click.echo("Clean complete.")


@main.command()
def report() -> None:
    """Generate report from experiment results."""
    state_dir = Path.cwd() / "state"
    if not state_dir.exists():
        click.echo("No active project.")
        return

    report_dir = Path.cwd() / "report"
    report_dir.mkdir(exist_ok=True)

    results = read_results(state_dir)
    log = read_strategist_log(state_dir)

    baseline = read_baseline_holdout(state_dir)
    baseline_note = ""
    if not baseline:
        baseline_note = "\n> **Note:** Baseline holdout results were not captured.\n"

    keeps = [r for r in results if r["status"] == "keep"]
    discards = [r for r in results if r["status"] == "discard"]
    crashes = [r for r in results if r["status"] == "crash"]

    report_content = f"""# MengerFlock Experimentation Report

**Generated:** {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")}
{baseline_note}
## Summary

- Total experiments: {len(results)}
- Keeps: {len(keeps)}
- Discards: {len(discards)}
- Crashes: {len(crashes)}
- Strategist actions: {len(log)}

## Experiment Log

| Timestamp | Researcher | Module | Status | Hypothesis |
|---|---|---|---|---|
"""
    for r in results:
        report_content += f"| {r.get('timestamp', '')} | {r.get('researcher', '')} | {r.get('module', '')} | {r.get('status', '')} | {r.get('hypothesis', '')} |\n"

    report_content += "\n## Strategist Log\n\n"
    for entry in log:
        report_content += f"- **{entry.get('timestamp', '')}** {entry.get('action', '')}: {entry.get('details', '')}\n"

    report_path = report_dir / "experimentation-report.md"
    report_path.write_text(report_content)
    click.echo(f"Experimentation report: {report_path}")

    if baseline and keeps:
        best = min(keeps, key=lambda r: float(r["metric_avg"]))
        baseline_avg = float(baseline[0]["metric_avg"])
        if float(best["metric_avg"]) < baseline_avg:
            click.echo("Evolved algorithm beats baseline — research paper should be produced by strategist.")
        else:
            click.echo("Evolved algorithm did not beat baseline — no research paper.")
    else:
        click.echo("Insufficient data for holdout comparison.")
