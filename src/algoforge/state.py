from __future__ import annotations

import csv
import fcntl
from datetime import datetime, timezone
from pathlib import Path

import yaml

RESULTS_HEADER = [
    "timestamp", "researcher", "module", "commit",
    "metric_avg", "metric_best", "status", "hypothesis", "description",
]

STRATEGIST_LOG_HEADER = ["timestamp", "action", "details"]


def init_state_dir(state_dir: str | Path) -> None:
    state_dir = Path(state_dir)
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "assignments").mkdir(exist_ok=True)

    results_path = state_dir / "results.tsv"
    if not results_path.exists():
        results_path.write_text("\t".join(RESULTS_HEADER) + "\n")

    log_path = state_dir / "strategist_log.tsv"
    if not log_path.exists():
        log_path.write_text("\t".join(STRATEGIST_LOG_HEADER) + "\n")


def _append_tsv(path: Path, row: list[str]) -> None:
    with open(path, "a") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            f.write("\t".join(str(v) for v in row) + "\n")
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def _read_tsv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path) as f:
        reader = csv.DictReader(f, delimiter="\t")
        return list(reader)


def append_result(state_dir: str | Path, result: dict) -> None:
    state_dir = Path(state_dir)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    row = [
        ts, result["researcher"], result["module"], result["commit"],
        result["metric_avg"], result["metric_best"], result["status"],
        result["hypothesis"], result["description"],
    ]
    _append_tsv(state_dir / "results.tsv", row)


def read_results(state_dir: str | Path) -> list[dict]:
    return _read_tsv(Path(state_dir) / "results.tsv")


def append_strategist_log(state_dir: str | Path, action: str, details: str) -> None:
    state_dir = Path(state_dir)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    _append_tsv(state_dir / "strategist_log.tsv", [ts, action, details])


def read_strategist_log(state_dir: str | Path) -> list[dict]:
    return _read_tsv(Path(state_dir) / "strategist_log.tsv")


def write_assignment(state_dir: str | Path, researcher_id: str, assignment: dict) -> None:
    path = Path(state_dir) / "assignments" / f"{researcher_id}.yaml"
    path.write_text(yaml.dump(assignment, default_flow_style=False))


def read_assignment(state_dir: str | Path, researcher_id: str) -> dict:
    path = Path(state_dir) / "assignments" / f"{researcher_id}.yaml"
    return yaml.safe_load(path.read_text())


def write_shutdown_flag(state_dir: str | Path) -> None:
    (Path(state_dir) / "shutdown").touch()


def is_shutdown_requested(state_dir: str | Path) -> bool:
    return (Path(state_dir) / "shutdown").exists()
