from __future__ import annotations

from pathlib import Path

import click

from algoforge.config import load_config
from algoforge.orchestrator import Orchestrator, init_project
from algoforge.state import read_results, read_strategist_log, is_shutdown_requested


@click.group()
def main():
    """AlgoForge — automated algorithm discovery through multi-agent evolution."""
    pass


@main.command()
@click.option("--seed", type=click.Path(exists=True), help="Path to seed codebase")
@click.option("--config", "config_path", required=True, type=click.Path(exists=True))
def init(seed: str | None, config_path: str):
    """Initialize a new AlgoForge project."""
    config = load_config(config_path)
    project_dir = Path.cwd()

    if seed:
        config.project.seed_path = seed

    init_project(project_dir, config)
    click.echo(f"Project initialized: {config.project.name}")
    click.echo(f"State directory: {project_dir / 'state'}")


@main.command()
@click.argument("config_path", type=click.Path(exists=True))
def run(config_path: str):
    """Run the AlgoForge experiment."""
    config = load_config(config_path)
    project_dir = Path.cwd()

    if not (project_dir / "state").exists():
        init_project(project_dir, config)

    orchestrator = Orchestrator(project_dir, config)
    click.echo(f"Starting AlgoForge: {config.agents.researchers.count} researchers")
    orchestrator.run()


@main.command()
def status():
    """Show current experiment progress."""
    state_dir = Path.cwd() / "state"
    if not state_dir.exists():
        click.echo("No active project. Run 'algoforge init' first.")
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
def stop():
    """Gracefully stop the experiment."""
    state_dir = Path.cwd() / "state"
    if not state_dir.exists():
        click.echo("No active project.")
        return

    from algoforge.state import write_shutdown_flag
    write_shutdown_flag(state_dir)
    click.echo("Shutdown signal sent. Sessions will finish current iteration and stop.")


@main.command()
def report():
    """Generate report from experiment results."""
    state_dir = Path.cwd() / "state"
    if not state_dir.exists():
        click.echo("No active project.")
        return

    results = read_results(state_dir)
    log = read_strategist_log(state_dir)

    click.echo("=" * 60)
    click.echo("AlgoForge Experiment Report")
    click.echo("=" * 60)
    click.echo(f"\nTotal experiments: {len(results)}")
    click.echo(f"Strategist actions: {len(log)}")

    keeps = [r for r in results if r["status"] == "keep"]
    if keeps:
        best = min(keeps, key=lambda r: float(r["metric_avg"]))
        click.echo(f"\nBest result:")
        click.echo(f"  Module: {best['module']}")
        click.echo(f"  Commit: {best['commit']}")
        click.echo(f"  Metric (avg): {best['metric_avg']}")
        click.echo(f"  Hypothesis: {best['hypothesis']}")

    click.echo(f"\nFull results in: state/results.tsv")
    click.echo(f"Strategist log in: state/strategist_log.tsv")
