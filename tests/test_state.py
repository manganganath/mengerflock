from algoforge.state import (
    init_state_dir, append_result, read_results,
    append_strategist_log, read_strategist_log,
    write_assignment, read_assignment,
    write_shutdown_flag, is_shutdown_requested,
)


def test_init_state_dir(tmp_path):
    init_state_dir(tmp_path / "state")
    state_dir = tmp_path / "state"
    assert state_dir.exists()
    assert (state_dir / "results.tsv").exists()
    assert (state_dir / "strategist_log.tsv").exists()
    assert (state_dir / "assignments").is_dir()


def test_append_and_read_results(tmp_path):
    state_dir = tmp_path / "state"
    init_state_dir(state_dir)
    append_result(state_dir, {
        "researcher": "r1", "module": "mod_a", "commit": "abc1234",
        "metric_avg": 0.0012, "metric_best": 0.0008,
        "status": "keep", "hypothesis": "test hypothesis",
        "description": "test change",
    })
    results = read_results(state_dir)
    assert len(results) == 1
    assert results[0]["researcher"] == "r1"
    assert results[0]["status"] == "keep"
    assert float(results[0]["metric_avg"]) == 0.0012


def test_append_and_read_strategist_log(tmp_path):
    state_dir = tmp_path / "state"
    init_state_dir(state_dir)
    append_strategist_log(state_dir, "init", "Decomposed into 3 modules")
    log = read_strategist_log(state_dir)
    assert len(log) == 1
    assert log[0]["action"] == "init"


def test_write_and_read_assignment(tmp_path):
    state_dir = tmp_path / "state"
    init_state_dir(state_dir)
    assignment = {
        "module_name": "move_operators",
        "files": ["SRC/Best2OptMove.c"],
        "objective": "Improve k-opt move selection",
        "constraints": ["Do not change function signatures"],
        "context": "Previous attempts focused on sorting",
    }
    write_assignment(state_dir, "r1", assignment)
    loaded = read_assignment(state_dir, "r1")
    assert loaded["module_name"] == "move_operators"
    assert loaded["files"] == ["SRC/Best2OptMove.c"]


def test_shutdown_flag(tmp_path):
    state_dir = tmp_path / "state"
    init_state_dir(state_dir)
    assert not is_shutdown_requested(state_dir)
    write_shutdown_flag(state_dir)
    assert is_shutdown_requested(state_dir)


def test_read_results_empty(tmp_path):
    state_dir = tmp_path / "state"
    init_state_dir(state_dir)
    results = read_results(state_dir)
    assert results == []
